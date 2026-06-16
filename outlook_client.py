import json
import os
import time
from datetime import datetime, timedelta, timezone

import msal
import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.ReadWrite"]
TOKEN_FILE = "outlook_token.json"


def get_outlook_credentials() -> dict:
    """
    Acquire an access token via MSAL device-code or interactive flow.
    Persists the token cache in outlook_token.json so re-authentication
    is only needed when the refresh token expires (~90 days for Microsoft).
    """
    client_id = os.getenv("OUTLOOK_CLIENT_ID")
    tenant_id = os.getenv("OUTLOOK_TENANT_ID", "common")

    if not client_id:
        raise ValueError(
            "OUTLOOK_CLIENT_ID is not set in .env.\n"
            "Register an app in Azure Portal and add the client ID."
        )

    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )

    token_result = None

    # Try silent acquisition first (uses cached refresh token)
    accounts = app.get_accounts()
    if accounts:
        token_result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not token_result:
        # Interactive browser login
        token_result = app.acquire_token_interactive(scopes=SCOPES)

    if "error" in token_result:
        raise RuntimeError(
            f"Outlook authentication failed: {token_result.get('error_description')}"
        )

    # Persist updated cache
    if cache.has_state_changed:
        with open(TOKEN_FILE, "w") as f:
            f.write(cache.serialize())

    return token_result


class OutlookClient:
    def __init__(self, token_result: dict):
        self._token_result = token_result
        self._client_id = os.getenv("OUTLOOK_CLIENT_ID")
        self._tenant_id = os.getenv("OUTLOOK_TENANT_ID", "common")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token_result['access_token']}",
            "Content-Type": "application/json",
        }

    def _get(self, url: str, params: dict = None) -> dict:
        """GET with retry on 429."""
        for attempt in range(3):
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limit hit, retrying in {retry_after}s... (attempt {attempt + 1})")
                time.sleep(retry_after)
                continue
            if resp.status_code == 401:
                # Token expired mid-session — refresh silently
                self._refresh_token()
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Failed to GET {url} after 3 attempts")

    def _patch(self, url: str, body: dict) -> None:
        """PATCH with retry on 429."""
        for attempt in range(3):
            resp = requests.patch(url, headers=self._headers(), json=body, timeout=30)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limit hit on PATCH, retrying in {retry_after}s... (attempt {attempt + 1})")
                time.sleep(retry_after)
                continue
            if not resp.ok:
                print(f"  PATCH {url} failed: {resp.status_code} {resp.text[:200]}")
            return

    def _refresh_token(self) -> None:
        cache = msal.SerializableTokenCache()
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as f:
                cache.deserialize(f.read())

        app = msal.PublicClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            token_cache=cache,
        )
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._token_result = result
                if cache.has_state_changed:
                    with open(TOKEN_FILE, "w") as f:
                        f.write(cache.serialize())

    def fetch_recent_emails(self) -> list[dict]:
        """Fetch unread emails received in the last 24 hours from the inbox."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        params = {
            "$filter": f"isRead eq false and receivedDateTime ge {yesterday}",
            "$select": "id,subject,from,receivedDateTime,body",
            "$top": "50",
        }

        data = self._get(f"{GRAPH_BASE}/me/mailFolders/inbox/messages", params=params)
        messages = data.get("value", [])

        emails = []
        for msg in messages:
            sender = msg.get("from", {}).get("emailAddress", {})
            sender_name = sender.get("name", "")
            sender_email = sender.get("address", "")
            subject = msg.get("subject", "(no subject)")
            date_str = msg.get("receivedDateTime", "")
            body_content = msg.get("body", {}).get("content", "")

            # Strip HTML tags for plain-text body
            import re
            body_text = re.sub(r"<[^>]+>", " ", body_content)
            body_text = re.sub(r"\s+", " ", body_text).strip()

            emails.append({
                "id": msg["id"],
                "subject": subject,
                "sender_name": sender_name,
                "sender_email": sender_email,
                "date": date_str[:10] if date_str else "",
                "body": body_text,
            })

        return emails

    def mark_as_read(self, msg_id: str) -> None:
        """Mark a message as read."""
        self._patch(
            f"{GRAPH_BASE}/me/messages/{msg_id}",
            {"isRead": True},
        )
