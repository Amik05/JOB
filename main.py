import sys

from dotenv import load_dotenv

load_dotenv()

from classifier import Classifier
from gmail_client import GmailClient, get_credentials
from scheduler import Scheduler
from sheets_client import SheetsClient


def main() -> None:
    print("=" * 50)
    print("  J*B — Job Application Monitor")
    print("=" * 50)

    print("\nAuthenticating with Google...")
    try:
        creds = get_credentials()
    except FileNotFoundError:
        print(
            "\nERROR: credentials.json not found.\n"
            "Download it from Google Cloud Console (OAuth 2.0 Desktop App)\n"
            "and place it in the project root directory."
        )
        sys.exit(1)

    print("Initialising clients...")
    gmail = GmailClient(creds)
    sheets = SheetsClient(creds)
    classifier = Classifier()

    print("\nJ*B is running. Monitoring your inbox every 2 hours.")
    print("(Press Ctrl+C at any time to stop)\n")

    scheduler = Scheduler(gmail, sheets, classifier)
    scheduler.start()


if __name__ == "__main__":
    main()
