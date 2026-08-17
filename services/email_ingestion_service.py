import logging
import uuid

from db.repository import (
    fetch_invoice_original_sender,
    find_invoice_by_work_id,
    get_connection,
    insert_email,
    insert_email_scan,
    insert_outbox_only,
    insert_work_item_and_document,
    insert_work_item_and_helpdesk,
    insert_work_item_and_rejected_helpdesk,
    mark_status,
)
from services.email_classification import extract_work_id, same_sender
from clients.gmail_client import (
    ParsedEmail,
    connect,
    expunge_and_logout,
    fetch_unread_messages,
    mark_seen,
    move_to_folder,
)
from clients.s3_client import upload_attachment_bytes
from logging_config import trace

log = logging.getLogger("ap_agent.ingestion")

PROCESSED_FOLDER = "Processed"
MAX_EMAILS_PER_SCAN = 50


def _format_email_content(parsed: ParsedEmail) -> str:
    return f"Date: {parsed.date}\n\n{parsed.body}"


def _record_attachment(conn, email_id: str, attachment) -> None:
    work_id = str(uuid.uuid4())
    with trace(work_id):
        try:
            document_link = upload_attachment_bytes(
                work_id, attachment.filename, attachment.content_bytes
            )
            insert_work_item_and_document(conn, work_id, email_id, document_link)
            log.info("recorded %s -> %s", attachment.filename, document_link)
        except Exception:
            log.exception("failed to record attachment %r", attachment.filename)


def _record_invoice_email(conn, scan_id: str, parsed: ParsedEmail) -> bool:
    """Returns True if the email was recorded (regardless of whether every
    attachment on it also succeeded) -- callers use this to decide whether
    the source email is safe to move out of the inbox."""
    try:
        email_id = insert_email(
            conn, scan_id, parsed.sender, parsed.subject, _format_email_content(parsed)
        )
    except Exception:
        log.exception("failed to record email %r", parsed.subject)
        return False

    for attachment in parsed.attachments:
        _record_attachment(conn, email_id, attachment)

    return True


def _record_helpdesk_email(conn, scan_id: str, parsed: ParsedEmail, invoice_work_id: str) -> bool:
    """Returns True if this no-attachment, work_id-referencing email was
    recorded as a HELPDESK work item linked to invoice_work_id."""
    try:
        email_id = insert_email(
            conn, scan_id, parsed.sender, parsed.subject, _format_email_content(parsed)
        )
    except Exception:
        log.exception("failed to record helpdesk email %r", parsed.subject)
        return False

    work_id = str(uuid.uuid4())
    with trace(work_id):
        try:
            insert_work_item_and_helpdesk(conn, work_id, email_id, invoice_work_id)
            log.info("recorded helpdesk query %r -> invoice %s", parsed.subject, invoice_work_id)
            return True
        except Exception:
            log.exception("failed to record helpdesk work item")
            return False


def _record_rejected_helpdesk_email(
    conn, scan_id: str, parsed: ParsedEmail, invoice_work_id: str, original_sender: str
) -> bool:
    """Same shape as _record_helpdesk_email, but for a work_id reference
    that failed the sender-match check -- recorded as HELPDESK_REJECTED
    (visible in the dashboard's Activity Logs, factored into the pipeline
    success rate) instead of silently vanishing into the 'other' queue.
    Never pushed to the helpdesk SQS queue, so the LLM never sees it and
    no reply is ever sent."""
    try:
        email_id = insert_email(
            conn, scan_id, parsed.sender, parsed.subject, _format_email_content(parsed)
        )
    except Exception:
        log.exception("failed to record rejected helpdesk email %r", parsed.subject)
        return False

    work_id = str(uuid.uuid4())
    with trace(work_id):
        try:
            insert_work_item_and_rejected_helpdesk(conn, work_id, email_id, invoice_work_id)
            mark_status(
                conn, work_id, "HELPDESK_REJECTED",
                detail=(
                    f"sender {parsed.sender!r} does not match invoice {invoice_work_id}'s "
                    f"original sender {original_sender!r}"
                ),
            )
            log.warning(
                "rejected helpdesk query %r -> invoice %s (sender mismatch)",
                parsed.subject, invoice_work_id,
            )
            return True
        except Exception:
            log.exception("failed to record rejected helpdesk work item")
            return False


def run_ingestion():
    """Classifies each unread email by (attachment present, work_id
    referenced in subject/body):
      - has an attachment                 -> INVOICE, regardless of work_id.
      - no attachment, work_id referenced -> HELPDESK, linked to that
        invoice, if the referenced work_id is actually an
        already-processed invoice (helpdesk rows require a non-null
        invoice_work_id) *and* the sender matches who originally
        submitted it -- a work_id that resolves to a real invoice but
        was referenced by a different sender is recorded as
        HELPDESK_REJECTED (visible, not silently dropped) rather than
        answered.
      - anything else (no attachment and no work_id, or a work_id that
        isn't a known invoice at all) -> routed to the 'other' outbox
        queue for visibility, then marked read so it isn't re-checked
        forever. No work_item is created for these -- there's nothing to
        point one at.
    """
    mail = connect()

    try:
        parsed_emails = fetch_unread_messages(mail, max_messages=MAX_EMAILS_PER_SCAN)
        with_attachment = [p for p in parsed_emails if p.attachments]
        without_attachment = [p for p in parsed_emails if not p.attachments]

        work_id_candidates = []  # (parsed, referenced_work_id)
        other_candidates = []   # parsed emails with nothing to classify them
        for parsed in without_attachment:
            referenced_work_id = extract_work_id(parsed.subject, parsed.body)
            if referenced_work_id is None:
                other_candidates.append(parsed)
            else:
                work_id_candidates.append((parsed, referenced_work_id))

        if not with_attachment and not work_id_candidates and not other_candidates:
            log.info("no emails this scan")
            return

        processed_eids = []

        with get_connection() as conn:
            # Resolve work_id candidates against known invoices now, while
            # a connection is open, so the scan's count_of_email reflects
            # only emails that actually get recorded as INVOICE/HELPDESK.
            helpdesk_candidates = []  # (parsed, invoice_work_id)
            rejected_candidates = []  # (parsed, invoice_work_id, original_sender)
            for parsed, referenced_work_id in work_id_candidates:
                invoice_work_id = find_invoice_by_work_id(conn, referenced_work_id)
                if invoice_work_id is None:
                    log.info(
                        "work_id %r referenced in %r is not a known invoice -- routed to 'other'",
                        referenced_work_id, parsed.subject,
                    )
                    other_candidates.append(parsed)
                    continue

                # work_ids are plain UUIDs quoted in plaintext reply
                # subjects -- anyone who sees one (forwarded, CC'd, or
                # simply guessed) could otherwise ask for that invoice's
                # details. Only the address that originally submitted the
                # invoice is allowed to raise a helpdesk query against it.
                original_sender = fetch_invoice_original_sender(conn, referenced_work_id)
                if not same_sender(original_sender, parsed.sender):
                    rejected_candidates.append((parsed, invoice_work_id, original_sender))
                    continue

                helpdesk_candidates.append((parsed, invoice_work_id))

            scan_id = insert_email_scan(
                conn, len(with_attachment) + len(helpdesk_candidates) + len(rejected_candidates)
            )
            with trace(scan_id):
                log.info(
                    "scan found %d invoice email(s), %d helpdesk email(s), "
                    "%d rejected helpdesk email(s), %d other email(s)",
                    len(with_attachment), len(helpdesk_candidates),
                    len(rejected_candidates), len(other_candidates),
                )

                for parsed in with_attachment:
                    if _record_invoice_email(conn, scan_id, parsed):
                        processed_eids.append(parsed.eid)

                for parsed, invoice_work_id in helpdesk_candidates:
                    if _record_helpdesk_email(conn, scan_id, parsed, invoice_work_id):
                        processed_eids.append(parsed.eid)

                for parsed, invoice_work_id, original_sender in rejected_candidates:
                    if _record_rejected_helpdesk_email(conn, scan_id, parsed, invoice_work_id, original_sender):
                        processed_eids.append(parsed.eid)

                # 'other' emails aren't durable business records -- no
                # work_item is created for them -- so they're marked seen
                # immediately rather than added to processed_eids (which
                # would move them to PROCESSED_FOLDER, a folder meant for
                # emails that produced an actual invoice/helpdesk record).
                for parsed in other_candidates:
                    insert_outbox_only(
                        conn, "other",
                        {"sender": parsed.sender, "subject": parsed.subject, "date": parsed.date},
                    )
                    mark_seen(mail, parsed.eid)

        # Only move emails whose rows are durably committed -- if we crash
        # before this point, they're simply retried (still unread, still
        # in the inbox) on the next scan instead of being moved with no
        # trace in the DB.
        for eid in processed_eids:
            mark_seen(mail, eid)
            move_to_folder(mail, eid, PROCESSED_FOLDER)
    finally:
        expunge_and_logout(mail)
