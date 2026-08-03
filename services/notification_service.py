import traceback
from typing import Optional

from clients.mailer_client import send_email
from db.repository import fetch_sender_for_work_id

# Only these are terminal, sender-facing outcomes -- PO_NOT_FOUND,
# PO_VALIDATED, PO_VALIDATION_MISMATCH, VENDOR_MATCHED, VENDOR_NEW etc.
# are internal operational signals, not something to put in front of the
# person who emailed the invoice in.
_NOTIFIABLE_STATUSES = {"EXTRACTION_COMPLETED", "EXTRACTION_FAILED", "SKIPPED"}


def _build_body(work_id: str, status: str, detail: Optional[str]) -> str:
    if status == "EXTRACTION_COMPLETED":
        return (
            "Your invoice has been received and processed successfully.\n\n"
            f"Reference: {work_id}"
        )
    if status == "SKIPPED":
        # detail is already the fully-composed decline reply from
        # validation.build_duplicate_decline_reply -- send it as-is.
        return detail or f"This invoice (reference {work_id}) has already been processed."
    if status == "EXTRACTION_FAILED":
        return (
            "We were unable to process your invoice.\n\n"
            f"Reference: {work_id}\n"
            f"Reason: {detail or 'Unknown error'}"
        )
    return f"Status update for reference {work_id}: {status}"


def notify_sender(conn, work_id: str, status: str, detail: Optional[str] = None) -> None:
    """Best-effort: emails the original sender a status update once a
    work_id reaches a terminal state. Never raises -- a failed
    notification shouldn't undo or block the invoice processing result,
    which has already been committed by the time this is called."""
    if status not in _NOTIFIABLE_STATUSES:
        return

    try:
        sender = fetch_sender_for_work_id(conn, work_id)
        if sender is None:
            print(f"[{work_id}] no sender found -- skipping status notification")
            return

        subject = f"Re: {sender['email_subject']} [Ref: {work_id}]"
        body = _build_body(work_id, status, detail)

        send_email(sender["email_from"], subject, body)
        print(f"[{work_id}] status notification ({status}) sent to {sender['email_from']}")
    except Exception:
        print(f"[{work_id}] failed to send status notification:")
        traceback.print_exc()
