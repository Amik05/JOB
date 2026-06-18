import json
import os
import time
import base64
import email
from datetime import datetime, timedelta
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_credentials() -> Credentials:
    """
    Load OAuth credentials. Priority order:
    1. GOOGLE_TOKEN_JSON env var (used in cloud/headless environments)
    2. token.json file on disk (used locally)
    3. Interactive browser flow (first-time local setup only)
    """
    creds = None

    token_json_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json_env:
        # Cloud mode: token is stored as an environment variable
        creds = Credentials.from_authorized_user_info(
            json.loads(token_json_env), SCOPES
        )
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Persist refreshed token back to env source or file
            if token_json_env:
                # Print reminder — in Railway update the env var with the new value
                print("  Token refreshed. Update GOOGLE_TOKEN_JSON in Railway with:")
                print(f"  {creds.to_json()}")
            else:
                with open(TOKEN_FILE, "w") as token_file:
                    token_file.write(creds.to_json())
        else:
            if token_json_env:
                raise RuntimeError(
                    "GOOGLE_TOKEN_JSON is set but the token is invalid and cannot be "
                    "refreshed headlessly. Re-authenticate locally and update the env var."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())

    return creds


class GmailClient:
    def __init__(self, creds: Credentials):
        self.service = build("gmail", "v1", credentials=creds)

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain-text body from a Gmail message payload."""
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result

        return ""

    def _fetch_message(self, msg_id: str) -> Optional[dict]:
        """Fetch a single message with retry on rate limit."""
        for attempt in range(3):
            try:
                return self.service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()
            except HttpError as e:
                if e.resp.status == 429:
                    print(f"  Rate limit hit, retrying in 5s... (attempt {attempt + 1})")
                    time.sleep(5)
                else:
                    print(f"  Gmail API error fetching message {msg_id}: {e}")
                    return None
        return None

    def fetch_recent_emails(self) -> list[dict]:
        """Fetch unread emails from the last 24 hours in the primary category."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y/%m/%d")
        query = f"is:unread category:primary after:{yesterday}"

        try:
            response = self.service.users().messages().list(
                userId="me", q=query
            ).execute()
        except HttpError as e:
            print(f"Failed to list Gmail messages: {e}")
            return []

        messages = response.get("messages", [])
        if not messages:
            return []

        emails = []
        for msg_stub in messages:
            msg = self._fetch_message(msg_stub["id"])
            if not msg:
                continue

            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            subject = headers.get("Subject", "(no subject)")
            from_header = headers.get("From", "")
            date_str = headers.get("Date", "")
            body = self._extract_body(msg["payload"])

            # Parse sender name and email from "Name <email>" format
            sender_name = from_header
            sender_email = from_header
            if "<" in from_header and ">" in from_header:
                sender_name = from_header.split("<")[0].strip().strip('"')
                sender_email = from_header.split("<")[1].rstrip(">").strip()

            emails.append({
                "id": msg["id"],
                "subject": subject,
                "sender_name": sender_name,
                "sender_email": sender_email,
                "date": date_str,
                "body": body,
            })

        return emails

    def mark_as_read(self, msg_id: str) -> None:
        """Remove the UNREAD label from a message."""
        for attempt in range(3):
            try:
                self.service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
                return
            except HttpError as e:
                if e.resp.status == 429:
                    print(f"  Rate limit hit on mark-as-read, retrying in 5s... (attempt {attempt + 1})")
                    time.sleep(5)
                else:
                    print(f"  Failed to mark message {msg_id} as read: {e}")
                    return
