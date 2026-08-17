"""Read-only queries backing the dashboard API (api/app.py). Kept separate
from db/repository.py, which is the write-path/business-logic layer the
workers use -- these are purely for display and never mutate anything."""

import psycopg2.extras

_DictCursor = psycopg2.extras.RealDictCursor


def fetch_metrics(conn) -> dict:
    with conn.cursor(cursor_factory=_DictCursor) as cur:
        cur.execute("SELECT count(*) AS n FROM invoice")
        total_invoices = cur.fetchone()["n"]

        cur.execute("SELECT count(*) AS n FROM helpdesk")
        total_helpdesk_queries = cur.fetchone()["n"]

        cur.execute("SELECT count(*) AS n FROM email")
        total_emails = cur.fetchone()["n"]

        cur.execute(
            """
            SELECT count(*) AS n FROM email e
            JOIN email_scan es ON es.scan_id = e.scan_id
            WHERE es.scanned_at >= current_date
            """
        )
        emails_today = cur.fetchone()["n"]

        # Dominant currency's total, so the headline number isn't a
        # meaningless sum across mismatched currencies -- most invoices
        # are expected to share one currency in practice.
        cur.execute(
            """
            SELECT invoice_currency, sum(total_amount) AS total, count(*) AS n
            FROM invoice
            GROUP BY invoice_currency
            ORDER BY n DESC
            LIMIT 1
            """
        )
        currency_row = cur.fetchone()

        # Success rate over INVOICE work items only -- work_execution also
        # holds HELPDESK_ANSWERED/HELPDESK_FAILED rows, which aren't part
        # of "invoice extraction succeeded" and would skew this otherwise.
        cur.execute(
            """
            SELECT we.status, count(*) AS n
            FROM work_execution we
            JOIN work_item wi ON wi.work_id = we.work_id
            WHERE wi.process_type = 'INVOICE'
            GROUP BY we.status
            """
        )
        status_counts = {row["status"]: row["n"] for row in cur.fetchall()}

    completed = status_counts.get("EXTRACTION_COMPLETED", 0)
    terminal_total = sum(
        status_counts.get(s, 0) for s in ("EXTRACTION_COMPLETED", "EXTRACTION_FAILED", "SKIPPED")
    )
    success_rate = (completed / terminal_total * 100) if terminal_total else None

    return {
        "total_invoices": total_invoices,
        "total_helpdesk_queries": total_helpdesk_queries,
        "total_emails": total_emails,
        "emails_today": emails_today,
        "total_invoice_value": float(currency_row["total"]) if currency_row and currency_row["total"] is not None else 0.0,
        "total_invoice_value_currency": currency_row["invoice_currency"] if currency_row else None,
        "success_rate": round(success_rate, 1) if success_rate is not None else None,
        "status_breakdown": status_counts,
    }


def fetch_email_volume_trend(conn, days: int = 14) -> list:
    with conn.cursor(cursor_factory=_DictCursor) as cur:
        cur.execute(
            """
            SELECT date_trunc('day', es.scanned_at) AS day, count(*) AS count
            FROM email e
            JOIN email_scan es ON es.scan_id = e.scan_id
            WHERE es.scanned_at >= now() - (%s || ' days')::interval
            GROUP BY day
            ORDER BY day
            """,
            (days,),
        )
        return [{"day": row["day"].date().isoformat(), "count": row["count"]} for row in cur.fetchall()]


_EMAIL_LIST_BASE = """
    SELECT e.email_id, e.email_from, e.email_subject, es.scanned_at,
           wi.process_type, we.status
    FROM email e
    JOIN email_scan es ON es.scan_id = e.scan_id
    LEFT JOIN LATERAL (
        SELECT work_id, process_type FROM work_item WHERE email_id = e.email_id LIMIT 1
    ) wi ON true
    LEFT JOIN work_execution we ON we.work_id = wi.work_id
"""


def _serialize_email_row(row: dict) -> dict:
    return {
        "email_id": row["email_id"],
        "sender": row["email_from"],
        "subject": row["email_subject"],
        "received_at": row["scanned_at"].isoformat() if row["scanned_at"] else None,
        "type": row["process_type"] or "OTHER",
        "status": row["status"],
    }


def fetch_recent_emails(conn, limit: int = 5) -> list:
    with conn.cursor(cursor_factory=_DictCursor) as cur:
        cur.execute(_EMAIL_LIST_BASE + " ORDER BY es.scanned_at DESC LIMIT %s", (limit,))
        return [_serialize_email_row(row) for row in cur.fetchall()]


def fetch_emails_page(conn, page: int, page_size: int) -> dict:
    offset = (page - 1) * page_size
    with conn.cursor(cursor_factory=_DictCursor) as cur:
        cur.execute("SELECT count(*) AS n FROM email")
        total = cur.fetchone()["n"]

        cur.execute(
            _EMAIL_LIST_BASE + " ORDER BY es.scanned_at DESC LIMIT %s OFFSET %s",
            (page_size, offset),
        )
        rows = [_serialize_email_row(row) for row in cur.fetchall()]

    return {"emails": rows, "total": total, "page": page, "page_size": page_size}
