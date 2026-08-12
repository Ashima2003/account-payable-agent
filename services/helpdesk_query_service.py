import asyncio
import logging
import time

from google import genai
from google.genai import types

import config
from clients.mailer_client import send_email
from clients.mcp_db_client import open_session
from db.repository import append_log, fetch_helpdesk_query, get_connection, mark_status
from logging_config import trace

log = logging.getLogger("ap_agent.helpdesk")

# Only the tables ap_helpdesk_readonly has SELECT on (see the GRANT in
# invoice-helpdesk-workflow-schema.sql's read-only role setup), and only
# the columns relevant to answering a vendor's question -- given directly
# instead of via a schema-introspection tool, since describe_table/
# list_tables both read crdb_internal/system catalogs that this role isn't
# granted access to (see clients/mcp_db_client.py).
_SCHEMA = """\
work_execution(work_id UUID, status STRING, updated_at TIMESTAMPTZ)
  -- current status per work item, e.g. EXTRACTION_STARTED, EXTRACTION_COMPLETED, EXTRACTION_FAILED, SKIPPED
work_execution_log(work_id UUID, timestamp TIMESTAMPTZ, status STRING, detail STRING)
  -- full append-only status history for a work item
invoice(invoice_work_id UUID, invoice_number STRING, invoice_date DATE, vendor_name STRING, total_amount DECIMAL, invoice_currency STRING, purchase_order STRING)
line_item(invoice_work_id UUID, line_number INT, description STRING, quantity DECIMAL, unit_price DECIMAL, line_amount DECIMAL)
helpdesk(helpdesk_work_id UUID, invoice_work_id UUID)
email(email_id UUID, email_from STRING, email_subject STRING, email_content STRING)
work_item(work_id UUID, email_id UUID, process_type STRING, created_at TIMESTAMPTZ)
"""

_SYSTEM_PROMPT = (
    "You are an accounts-payable helpdesk assistant replying to a vendor's "
    "email about invoice work_id {invoice_work_id}. You have one read-only "
    "SQL tool, execute_query(query), against this CockroachDB schema:\n\n"
    f"{_SCHEMA}\n"
    "Use it to look up whatever you need to answer -- never guess or "
    "fabricate figures, dates, or statuses. Answer only using data you "
    "actually retrieved. If you can't find anything relevant, say so "
    "plainly rather than speculating. Write the reply as plain email body "
    "text: no markdown, no subject line.\n\n"
    "Be efficient: one query joining the tables you need is almost always "
    "enough. As soon as a query succeeds and returns the data you need, "
    "write your final answer immediately -- do not re-run the same or a "
    "similar query again to double-check, and do not explore the schema "
    "with COUNT(*)/LIMIT/SELECT * queries. You have a hard cap of a few "
    "tool calls; running out without answering fails the whole request."
)


async def _generate_answer(invoice_work_id: str, question: str) -> str:
    if not config.LLM_API_KEY:
        raise RuntimeError("Please set the LLM_API_KEY environment variable.")

    async with open_session() as session:
        client = genai.Client(api_key=config.LLM_API_KEY)
        log.info("llm generate_content model=%s invoice_work_id=%s", config.LLM_MODEL, invoice_work_id)
        start = time.monotonic()
        response = await client.aio.models.generate_content(
            model=config.LLM_MODEL,
            contents=(
                f"{_SYSTEM_PROMPT.format(invoice_work_id=invoice_work_id)}\n\n"
                f"Vendor's question:\n{question}"
            ),
            config={"tools": [session]},
        )
        usage = getattr(response, "usage_metadata", None)
        log.info(
            "llm generate_content completed (%.1fms) tokens=%s",
            (time.monotonic() - start) * 1000,
            usage.total_token_count if usage else "?",
        )
        if not response.text:
            # Happens if automatic function calling exhausts its remote-call
            # budget (default 10) while the model is still issuing tool
            # calls instead of answering -- response.text is then None, not
            # an exception, so this has to be checked explicitly or the
            # caller crashes deep inside smtplib.MIMEText(None) instead of
            # getting a clear, traceable failure reason.
            raise RuntimeError(
                "LLM produced no final text answer (likely exhausted its tool-call budget "
                "without settling on an answer) -- see the mcp call_tool log lines above"
            )
        return response.text


def answer_and_reply(helpdesk_work_id: str) -> None:
    with trace(helpdesk_work_id), get_connection() as conn:
        context = fetch_helpdesk_query(conn, helpdesk_work_id)
        if context is None:
            log.warning("no helpdesk row found -- skipping")
            return

        question = f"Subject: {context['email_subject']}\n\n{context['email_content']}"
        try:
            answer = asyncio.run(_generate_answer(context["invoice_work_id"], question))
            send_email(context["email_from"], f"Re: {context['email_subject']}", answer)
            append_log(conn, helpdesk_work_id, "HELPDESK_ANSWERED", detail=answer)
            mark_status(conn, helpdesk_work_id, "HELPDESK_ANSWERED")
            log.info("answered and replied to %r", context["email_from"])
        except Exception:
            mark_status(conn, helpdesk_work_id, "HELPDESK_FAILED")
            log.exception("failed to answer")
