"""
Single-run entry point used by GitHub Actions.
Runs one full scan and exits — the cron schedule in the workflow
handles the repeat interval instead of APScheduler.
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from classifier import Classifier
from gmail_client import GmailClient, get_credentials
from scheduler import run_job
from sheets_client import SheetsClient


def main() -> None:
    print("J*B — single scan starting...")

    try:
        creds = get_credentials()
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    gmail = GmailClient(creds)
    sheets = SheetsClient(creds)
    classifier = Classifier()

    run_job(gmail, sheets, classifier)
    print("Scan complete.")


if __name__ == "__main__":
    main()
