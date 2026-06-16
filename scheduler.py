from collections import Counter
from datetime import datetime
from typing import Protocol, runtime_checkable

from apscheduler.schedulers.blocking import BlockingScheduler

from classifier import Classifier
from sheets_client import SheetsClient


@runtime_checkable
class EmailClient(Protocol):
    def fetch_recent_emails(self) -> list[dict]: ...
    def mark_as_read(self, msg_id: str) -> None: ...


def run_job(gmail: EmailClient, sheets: SheetsClient, classifier: Classifier) -> None:
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running J*B scan...")

    emails = gmail.fetch_recent_emails()
    print(f"  Fetched {len(emails)} unread email(s) from the last 24 hours.")

    if not emails:
        print("  Nothing to process.")
        return

    processed = 0
    skipped = 0
    categories: Counter = Counter()

    for em in emails:
        result = classifier.classify(em)

        if result is None:
            skipped += 1
            gmail.mark_as_read(em["id"])
            continue

        action = sheets.upsert_email(result, em.get("date", ""))
        gmail.mark_as_read(em["id"])

        category = result.get("category", "unknown")
        company = result.get("company", "Unknown")
        role = result.get("role", "Unknown")

        categories[category] += 1
        processed += 1
        print(f"  [{action.upper()}] {company} — {role} ({category})")

    print(f"\n  Summary: {processed} processed, {skipped} skipped (not job-related).")
    if categories:
        for cat, count in categories.most_common():
            print(f"    {cat}: {count}")


class Scheduler:
    def __init__(
        self,
        gmail: EmailClient,
        sheets: SheetsClient,
        classifier: Classifier,
        interval_hours: int = 2,
    ):
        self.gmail = gmail
        self.sheets = sheets
        self.classifier = classifier
        self.interval_hours = interval_hours
        self._scheduler = BlockingScheduler(timezone="UTC")

    def start(self) -> None:
        # Run once immediately before the first scheduled interval
        run_job(self.gmail, self.sheets, self.classifier)

        self._scheduler.add_job(
            run_job,
            trigger="interval",
            hours=self.interval_hours,
            args=[self.gmail, self.sheets, self.classifier],
            misfire_grace_time=300,
        )

        print(f"\nNext scan scheduled in {self.interval_hours} hour(s). Press Ctrl+C to stop.")
        self._scheduler.start()
