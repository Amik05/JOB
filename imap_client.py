import email
import imaplib
import os
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Optional


def _decode_mime_words(value: str) -> str:
    """Decode encoded MIME header words (e.g. =?UTF-8?B?...?=)."""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_plain_text(msg: email.message.Message) -> str:
    """Walk a parsed email and return the first text/plain part."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(charset, errors="replace")
    return ""


class IMAPClient:
    def __init__(self):
        self.server = os.getenv("IMAP_SERVER", "outlook.office365.com")
        self.port = int(os.getenv("IMAP_PORT", "993"))
        self.username = os.getenv("IMAP_USERNAME", "")
        self.password = os.getenv("IMAP_PASSWORD", "")

        if not self.username or not self.password:
            raise ValueError(
                "IMAP_USERNAME and IMAP_PASSWORD must be set in .env.\n"
                "Use an app password if your account has MFA enabled."
            )

    def _connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.server, self.port)
        mail.login(self.username, self.password)
        mail.select("INBOX")
        return mail

    def fetch_recent_emails(self) -> list:
        """Fetch unread emails received in the last 24 hours."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d-%b-%Y")
        search_criteria = f'(UNSEEN SINCE "{yesterday}")'

        for attempt in range(3):
            try:
                mail = self._connect()
                status, data = mail.search(None, search_criteria)
                if status != "OK" or not data[0]:
                    mail.logout()
                    return []

                msg_ids = data[0].split()
                emails = []

                for msg_id in msg_ids:
                    status, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    subject = _decode_mime_words(msg.get("Subject", "(no subject)"))
                    from_header = _decode_mime_words(msg.get("From", ""))
                    date_str = msg.get("Date", "")
                    body = _extract_plain_text(msg)

                    # Parse "Name <email>" or plain address
                    sender_name = from_header
                    sender_email = from_header
                    if "<" in from_header and ">" in from_header:
                        sender_name = from_header.split("<")[0].strip().strip('"')
                        sender_email = from_header.split("<")[1].rstrip(">").strip()

                    # Parse date to YYYY-MM-DD
                    try:
                        parsed_date = email.utils.parsedate_to_datetime(date_str)
                        date_fmt = parsed_date.strftime("%Y-%m-%d")
                    except Exception:
                        date_fmt = date_str[:10] if date_str else ""

                    emails.append({
                        "id": msg_id.decode(),
                        "subject": subject,
                        "sender_name": sender_name,
                        "sender_email": sender_email,
                        "date": date_fmt,
                        "body": body,
                    })

                mail.logout()
                return emails

            except imaplib.IMAP4.error as e:
                print(f"  IMAP error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(5)

        return []

    def mark_as_read(self, msg_id: str) -> None:
        """Add the \\Seen flag to a message."""
        for attempt in range(3):
            try:
                mail = self._connect()
                mail.store(msg_id, "+FLAGS", "\\Seen")
                mail.logout()
                return
            except imaplib.IMAP4.error as e:
                print(f"  Failed to mark message {msg_id} as read (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(5)
