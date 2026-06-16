import os
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

HEADERS = [
    "Date",
    "Company",
    "Role",
    "Recruiter",
    "Recruiter Email",
    "Status",
    "Summary",
    "Next Action",
    "Urgency",
    "Suggested Reply",
]

# Column indices (0-based) for update targeting
COL_COMPANY = 1
COL_ROLE = 2
COL_STATUS = 5
COL_NEXT_ACTION = 7
COL_URGENCY = 8

STATUS_COLORS = {
    "offer_received":    {"red": 0.20, "green": 0.78, "blue": 0.35},
    "rejection":         {"red": 0.90, "green": 0.27, "blue": 0.27},
    "follow_up_needed":  {"red": 1.00, "green": 0.84, "blue": 0.10},
    "interview_invite":  {"red": 0.26, "green": 0.52, "blue": 0.96},
    "awaiting_response": {"red": 0.75, "green": 0.75, "blue": 0.75},
}


def _a1(row: int, col: int) -> str:
    """Convert 0-based (row, col) to A1 notation (1-based)."""
    col_letter = chr(ord("A") + col)
    return f"{col_letter}{row + 1}"


class SheetsClient:
    def __init__(self, creds: Credentials):
        self.service = build("sheets", "v4", credentials=creds)
        self.spreadsheet_id = os.getenv("SPREADSHEET_ID")
        if not self.spreadsheet_id:
            raise ValueError("SPREADSHEET_ID is not set in .env")
        self._ensure_headers()

    def _read_all_rows(self) -> list[list]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1",
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            print(f"  Sheets read error: {e}")
            return []

    def _ensure_headers(self) -> None:
        rows = self._read_all_rows()
        if not rows or rows[0] != HEADERS:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS]},
            ).execute()

    def _find_existing_row(self, rows: list, company: str, role: str) -> Optional[int]:
        """
        Return the 0-based row index of an existing entry matching company+role,
        or None if not found. Row 0 is the header.
        """
        company_lower = company.strip().lower()
        role_lower = role.strip().lower()

        for i, row in enumerate(rows[1:], start=1):
            row_company = row[COL_COMPANY].strip().lower() if len(row) > COL_COMPANY else ""
            row_role = row[COL_ROLE].strip().lower() if len(row) > COL_ROLE else ""
            if row_company == company_lower and row_role == role_lower:
                return i
        return None

    def _color_status_cell(self, row_index: int) -> None:
        """Apply background color to the Status cell based on its value."""
        rows = self._read_all_rows()
        if row_index >= len(rows):
            return

        row = rows[row_index]
        status_value = row[COL_STATUS] if len(row) > COL_STATUS else ""
        color = STATUS_COLORS.get(status_value)
        if not color:
            return

        sheet_id = self._get_sheet_id()
        requests = [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": COL_STATUS,
                    "endColumnIndex": COL_STATUS + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": color
                    }
                },
                "fields": "userEnteredFormat.backgroundColor",
            }
        }]
        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()
        except HttpError as e:
            print(f"  Failed to color status cell: {e}")

    def _get_sheet_id(self) -> int:
        """Get the numeric sheetId of Sheet1."""
        try:
            meta = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            for sheet in meta.get("sheets", []):
                if sheet["properties"]["title"] == "Sheet1":
                    return sheet["properties"]["sheetId"]
        except HttpError as e:
            print(f"  Failed to get sheet ID: {e}")
        return 0

    def upsert_email(self, classification: dict, email_date: str) -> str:
        """
        Insert a new row or update an existing one.
        Returns "added" or "updated".
        """
        company = classification.get("company", "Unknown")
        role = classification.get("role", "Unknown")
        category = classification.get("category", "awaiting_response")
        date_str = email_date or datetime.utcnow().strftime("%Y-%m-%d")

        row_data = [
            date_str,
            company,
            role,
            classification.get("recruiter_name", "Unknown"),
            classification.get("recruiter_email", "Unknown"),
            category,
            classification.get("summary", ""),
            classification.get("next_action", ""),
            classification.get("urgency", "medium"),
            classification.get("suggested_reply", ""),
        ]

        rows = self._read_all_rows()
        existing_idx = self._find_existing_row(rows, company, role)

        if existing_idx is not None:
            # Update status, next action, and urgency in the existing row
            updates = [
                {
                    "range": f"Sheet1!{_a1(existing_idx, COL_STATUS)}",
                    "values": [[category]],
                },
                {
                    "range": f"Sheet1!{_a1(existing_idx, COL_NEXT_ACTION)}",
                    "values": [[classification.get("next_action", "")]],
                },
                {
                    "range": f"Sheet1!{_a1(existing_idx, COL_URGENCY)}",
                    "values": [[classification.get("urgency", "medium")]],
                },
            ]
            try:
                self.service.spreadsheets().values().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"valueInputOption": "RAW", "data": updates},
                ).execute()
            except HttpError as e:
                print(f"  Failed to update row: {e}")
                return "error"
            self._color_status_cell(existing_idx)
            return "updated"
        else:
            # Append a new row
            try:
                result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range="Sheet1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row_data]},
                ).execute()
            except HttpError as e:
                print(f"  Failed to append row: {e}")
                return "error"

            # Determine the row index of the newly appended row
            updated_range = result.get("updates", {}).get("updatedRange", "")
            new_row_idx = len(rows)  # header is row 0, so first data row is 1
            if updated_range:
                try:
                    # Extract row number from range like "Sheet1!A5:J5"
                    start_cell = updated_range.split("!")[1].split(":")[0]
                    new_row_idx = int("".join(filter(str.isdigit, start_cell))) - 1
                except (IndexError, ValueError):
                    pass

            self._color_status_cell(new_row_idx)
            return "added"
