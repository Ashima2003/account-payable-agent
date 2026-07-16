import imaplib
import email
import os
from email.header import decode_header

from dotenv import load_dotenv

load_dotenv()

EMAIL = os.environ["EMAIL"]
APP_PASSWORD = os.environ["APP_PASSWORD"]

QUERY_FOLDER = "Query"
MAX_EMAILS = 5

mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(EMAIL, APP_PASSWORD)

mail.select("INBOX")

# Get all email IDs
status, data = mail.search(None, "ALL")

if status != "OK":
    print("Failed to fetch emails.")
    mail.logout()
    exit()

all_ids = data[0].split()

print(f"Total emails in inbox: {len(all_ids)}")

# Create Query folder if it doesn't exist
try:
    mail.create(QUERY_FOLDER)
except:
    pass


def decode(value):
    if value is None:
        return ""

    decoded, enc = decode_header(value)[0]

    if isinstance(decoded, bytes):
        return decoded.decode(enc or "utf-8", errors="ignore")

    return decoded


processed = 0

# Traverse from newest -> oldest
for eid in reversed(all_ids):

    if processed == MAX_EMAILS:
        break

    # Check if email is unread
    status, flags_data = mail.fetch(eid, "(FLAGS)")

    if status != "OK":
        continue

    flags = flags_data[0].decode()

    if "\\Seen" in flags:
        continue

    # Fetch email
    status, msg_data = mail.fetch(eid, "(RFC822)")

    if status != "OK":
        continue

    msg = email.message_from_bytes(msg_data[0][1])

    subject = decode(msg["Subject"])
    sender = decode(msg["From"])
    date = decode(msg["Date"])

    body = ""

    if msg.is_multipart():
        for part in msg.walk():

            if (
                part.get_content_type() == "text/plain"
                and "attachment" not in str(part.get("Content-Disposition"))
            ):

                payload = part.get_payload(decode=True)

                if payload:
                    body = payload.decode(errors="ignore")
                    break
    else:
        payload = msg.get_payload(decode=True)

        if payload:
            body = payload.decode(errors="ignore")

    print("=" * 80)
    print("From   :", sender)
    print("Subject:", subject)
    print("Date   :", date)
    print("-" * 80)
    print(body[:500].strip())
    print()

    # Mark as read
    mail.store(eid, "+FLAGS", "\\Seen")

    # Copy to Query folder
    result, _ = mail.copy(eid, QUERY_FOLDER)

    if result == "OK":
        # Delete original from Inbox
        mail.store(eid, "+FLAGS", "\\Deleted")

    processed += 1

# Permanently remove deleted emails
mail.expunge()

mail.logout()

print(f"\nProcessed {processed} unread emails.")