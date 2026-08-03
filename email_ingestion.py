import traceback
import uuid

from db import (
    find_invoice_work_id_by_po,
    get_connection,
    insert_email,
    insert_email_scan,
    insert_work_item_and_document,
    insert_work_item_and_helpdesk,
)
from email_classification import extract_po_number
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


def _record_invoice_email(conn, scan_id: str, parsed: ParsedEmail) -> bool:
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


def _record_helpdesk_email(conn, scan_id: str, parsed: ParsedEmail, invoice_work_id: str) -> bool:
    """Returns True if this no-attachment, PO-referencing email was
    recorded as a HELPDESK work item linked to invoice_work_id."""
    try:
        email_id = insert_email(
            conn, scan_id, parsed.sender, parsed.subject, _format_email_content(parsed)
        )
    except Exception:
        print(f"Failed to record helpdesk email {parsed.subject!r}:")
        traceback.print_exc()
        return False

    work_id = str(uuid.uuid4())
    try:
        insert_work_item_and_helpdesk(conn, work_id, email_id, invoice_work_id)
        print(f"[{work_id}] recorded helpdesk query {parsed.subject!r} -> invoice {invoice_work_id}")
        return True
    except Exception:
        print(f"[{work_id}] failed to record helpdesk work item:")
        traceback.print_exc()
        return False


def run_ingestion():
    """Classifies each unread email by (attachment present, PO number
    referenced in subject/body):
      - has an attachment            -> INVOICE, regardless of PO number.
      - no attachment, PO referenced -> HELPDESK, linked to the invoice
        that PO belongs to (only if that invoice has already been
        processed -- helpdesk rows require a non-null invoice_work_id).
      - no attachment, no PO found, or PO found but no matching invoice
        yet -> not recorded; marked read so it isn't re-checked forever.
    """
    mail = connect()

    try:
        parsed_emails = fetch_unread_messages(mail, max_messages=MAX_EMAILS_PER_SCAN)
        with_attachment = [p for p in parsed_emails if p.attachments]
        without_attachment = [p for p in parsed_emails if not p.attachments]

        po_candidates = []  # (parsed, po_number)
        for parsed in without_attachment:
            po_number = extract_po_number(parsed.subject, parsed.body)
            if po_number is None:
                # No attachment and nothing that looks like a PO reference
                # -> nothing to do with it.
                mark_seen(mail, parsed.eid)
            else:
                po_candidates.append((parsed, po_number))

        if not with_attachment and not po_candidates:
            print("No qualifying (invoice/helpdesk) emails this scan.")
            return

        processed_eids = []

        with get_connection() as conn:
            # Resolve PO candidates against known invoices now, while a
            # connection is open, so the scan's count_of_email reflects
            # only emails that actually get recorded.
            helpdesk_candidates = []  # (parsed, invoice_work_id)
            for parsed, po_number in po_candidates:
                invoice_work_id = find_invoice_work_id_by_po(conn, po_number)
                if invoice_work_id is None:
                    print(f"PO {po_number!r} referenced in {parsed.subject!r} has no matching invoice yet -- not recorded")
                    mark_seen(mail, parsed.eid)
                    continue
                helpdesk_candidates.append((parsed, invoice_work_id))

            scan_id = insert_email_scan(conn, len(with_attachment) + len(helpdesk_candidates))
            print(f"[{scan_id}] scan found {len(with_attachment)} invoice email(s), {len(helpdesk_candidates)} helpdesk email(s)")

            for parsed in with_attachment:
                if _record_invoice_email(conn, scan_id, parsed):
                    processed_eids.append(parsed.eid)

            for parsed, invoice_work_id in helpdesk_candidates:
                if _record_helpdesk_email(conn, scan_id, parsed, invoice_work_id):
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
