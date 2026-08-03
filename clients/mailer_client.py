import smtplib
from email.mime.text import MIMEText

import config


def send_email(to_address: str, subject: str, body: str) -> None:
    """Sends a plain-text email from the same Gmail account already used
    for IMAP ingestion -- Gmail app passwords are account-level, not
    protocol-specific, so the existing EMAIL/APP_PASSWORD work for SMTP
    too."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.EMAIL
    msg["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(config.EMAIL, config.APP_PASSWORD)
        smtp.send_message(msg)
