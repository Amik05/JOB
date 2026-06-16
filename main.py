import os
import sys

from dotenv import load_dotenv

load_dotenv()

from classifier import Classifier
from scheduler import Scheduler
from sheets_client import SheetsClient


def _build_email_client():
    provider = os.getenv("EMAIL_PROVIDER", "gmail").strip().lower()

    if provider == "outlook":
        from outlook_client import OutlookClient, get_outlook_credentials
        print("Authenticating with Microsoft (Outlook)...")
        try:
            token = get_outlook_credentials()
        except Exception as e:
            print(f"\nERROR: Outlook authentication failed — {e}")
            sys.exit(1)
        return OutlookClient(token)

    # Default: Gmail
    from gmail_client import GmailClient, get_credentials
    print("Authenticating with Google (Gmail)...")
    try:
        creds = get_credentials()
    except FileNotFoundError:
        print(
            "\nERROR: credentials.json not found.\n"
            "Download it from Google Cloud Console (OAuth 2.0 Desktop App)\n"
            "and place it in the project root directory."
        )
        sys.exit(1)
    return GmailClient(creds)


def _build_sheets_client():
    from gmail_client import get_credentials
    creds = get_credentials()
    return SheetsClient(creds)


def main() -> None:
    print("=" * 50)
    print("  J*B — Job Application Monitor")
    print("=" * 50)

    email_client = _build_email_client()

    print("Initialising Sheets client...")
    sheets = _build_sheets_client()
    classifier = Classifier()

    provider = os.getenv("EMAIL_PROVIDER", "gmail").strip().lower()
    print(f"\nJ*B is running ({provider}). Monitoring your inbox every 2 hours.")
    print("(Press Ctrl+C at any time to stop)\n")

    scheduler = Scheduler(email_client, sheets, classifier)
    scheduler.start()


if __name__ == "__main__":
    main()
