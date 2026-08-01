import traceback
import uuid

from db import get_connection, insert_email, insert_email_scan, insert_work_item_and_document
from gmail_connection import (
    ParsedEmail,
    connect,
    expunge_and_logout,
    fetch_unread_messages,
    mark_seen,
    move_to_folder,
)
from s3_client import upload_attachment_bytes

PROCESSED_FOLDER = "Processed"
MAX_EMAILS_PER_SCAN = 50


def _format_email_content(parsed: ParsedEmail) -> str:
    return f"Date: {parsed.date}\n\n{parsed.body}"


def _record_attachment(conn, email_id: str, attachment) -> None:
    work_id = str(uuid.uuid4())
    try:
        document_link = upload_attachment_bytes(
            work_id, attachment.filename, attachment.content_bytes
        )
        insert_work_item_and_document(conn, work_id, email_id, document_link)
        print(f"[{work_id}] recorded {attachment.filename} -> {document_link}")
    except Exception:
        print(f"[{work_id}] failed to record attachment {attachment.filename!r}:")
        traceback.print_exc()


def _record_email(conn, scan_id: str, parsed: ParsedEmail) -> bool:
    """Returns True if the email was recorded (regardless of whether every
    attachment on it also succeeded) -- callers use this to decide whether
    the source email is safe to move out of the inbox."""
    try:
        email_id = insert_email(
            conn, scan_id, parsed.sender, parsed.subject, _format_email_content(parsed)
        )
    except Exception:
        print(f"Failed to record email {parsed.subject!r}:")
        traceback.print_exc()
        return False

    for attachment in parsed.attachments:
        _record_attachment(conn, email_id, attachment)

    return True


def run_ingestion():
    mail = connect()

    try:
        parsed_emails = fetch_unread_messages(mail, max_messages=MAX_EMAILS_PER_SCAN)
        qualifying = [p for p in parsed_emails if p.attachments]
        non_qualifying = [p for p in parsed_emails if not p.attachments]

        # No invoice/document attachment -> mark read so it isn't
        # re-checked forever, but no DB rows and no move out of the inbox.
        for parsed in non_qualifying:
            mark_seen(mail, parsed.eid)

        if not qualifying:
            print("No qualifying (invoice/document) emails this scan.")
            return

        processed_eids = []

        with get_connection() as conn:
            scan_id = insert_email_scan(conn, len(qualifying))
            print(f"[{scan_id}] scan found {len(qualifying)} qualifying email(s)")

            for parsed in qualifying:
                if _record_email(conn, scan_id, parsed):
                    processed_eids.append(parsed.eid)

        # Only move emails whose rows are durably committed -- if we crash
        # before this point, they're simply retried (still unread, still
        # in the inbox) on the next scan instead of being moved with no
        # trace in the DB.
        for eid in processed_eids:
            mark_seen(mail, eid)
            move_to_folder(mail, eid, PROCESSED_FOLDER)
    finally:
        expunge_and_logout(mail)


if __name__ == "__main__":
    run_ingestion()
