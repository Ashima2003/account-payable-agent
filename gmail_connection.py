import imaplib
import email
import os
from email.header import decode_header
from typing import List, NamedTuple, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

EMAIL = os.environ["EMAIL"]
APP_PASSWORD = os.environ["APP_PASSWORD"]

# Attachments that count as an "invoice or document" for ingestion purposes.
QUALIFYING_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
QUALIFYING_EXTENSIONS = (".pdf", ".doc", ".docx")


class Attachment(NamedTuple):
    filename: str
    content_bytes: bytes


class ParsedEmail(NamedTuple):
    eid: bytes
    subject: str
    sender: str
    date: str
    body: str
    attachments: List[Attachment]


def decode(value) -> str:
    if value is None:
        return ""

    decoded, enc = decode_header(value)[0]

    if isinstance(decoded, bytes):
        return decoded.decode(enc or "utf-8", errors="ignore")

    return decoded


def connect() -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL, APP_PASSWORD)
    mail.select("INBOX")
    return mail


def _is_qualifying_attachment(content_type: str, filename: str) -> bool:
    if content_type in QUALIFYING_CONTENT_TYPES:
        return True
    return filename.lower().endswith(QUALIFYING_EXTENSIONS)


def _extract_body_and_attachments(msg) -> Tuple[str, List[Attachment]]:
    body = ""
    attachments: List[Attachment] = []

    if not msg.is_multipart():
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(errors="ignore")
        return body, attachments

    for part in msg.walk():
        if part.is_multipart():
            continue

        filename = decode(part.get_filename())
        content_type = part.get_content_type()

        if filename and _is_qualifying_attachment(content_type, filename):
            payload = part.get_payload(decode=True)
            if payload:
                attachments.append(Attachment(filename=filename, content_bytes=payload))
            continue

        if (
            not body
            and content_type == "text/plain"
            and "attachment" not in str(part.get("Content-Disposition"))
        ):
            payload = part.get_payload(decode=True)
            if payload:
                body = payload.decode(errors="ignore")

    return body, attachments


def fetch_unread_messages(mail, max_messages: Optional[int] = None) -> List[ParsedEmail]:
    """Read-only: fetches unread messages and parses them, without marking
    anything as seen or otherwise mutating mailbox state."""
    status, data = mail.search(None, "UNSEEN")
    if status != "OK":
        return []

    eids = list(reversed(data[0].split()))  # newest first
    if max_messages is not None:
        eids = eids[:max_messages]

    parsed_emails = []
    for eid in eids:
        status, msg_data = mail.fetch(eid, "(BODY.PEEK[])")
        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        body, attachments = _extract_body_and_attachments(msg)

        parsed_emails.append(
            ParsedEmail(
                eid=eid,
                subject=decode(msg["Subject"]),
                sender=decode(msg["From"]),
                date=decode(msg["Date"]),
                body=body,
                attachments=attachments,
            )
        )

    return parsed_emails


def mark_seen(mail, eid: bytes) -> None:
    mail.store(eid, "+FLAGS", "\\Seen")


def move_to_folder(mail, eid: bytes, folder: str) -> None:
    try:
        mail.create(folder)
    except imaplib.IMAP4.error:
        pass  # folder already exists

    result, _ = mail.copy(eid, folder)
    if result == "OK":
        mail.store(eid, "+FLAGS", "\\Deleted")


def expunge_and_logout(mail) -> None:
    mail.expunge()
    mail.logout()
