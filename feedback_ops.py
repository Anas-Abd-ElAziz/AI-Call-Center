import json
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from google.oauth2 import service_account
from googleapiclient.discovery import build

from call_logger import logger, log_event


SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class FeedbackRecord:
    caller_name: str
    caller_email: str
    satisfied: bool
    reason: str
    rating: int
    topic: str
    ticket_number: str
    created_at: str


def _load_google_credentials():
    creds_info = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if creds_info:
        info = json.loads(creds_info)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=SHEETS_SCOPE,
        )

    if creds_path:
        return service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=SHEETS_SCOPE,
        )

    raise ValueError(
        "Missing Google service account credentials. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_INFO."
    )


def append_feedback_to_sheet(record: FeedbackRecord) -> str:
    spreadsheet_id = (os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or "").strip()
    if not spreadsheet_id:
        raise ValueError("Missing GOOGLE_SHEETS_SPREADSHEET_ID.")

    target_range = (os.getenv("GOOGLE_SHEETS_RANGE") or "").strip()
    creds = _load_google_credentials()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    if not target_range:
        meta = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        first_sheet = ((meta.get("sheets") or [{}])[0].get("properties") or {}).get(
            "title"
        )
        if not first_sheet:
            raise RuntimeError("Unable to resolve sheet tab title for default range.")
        target_range = f"{first_sheet}!A:G"

    values = [
        [
            record.created_at,
            record.caller_name,
            record.caller_email,
            '=IF(A2="","","T-"&TEXT(COUNTA($A$2:A2),"0000"))',
            "Yes" if record.satisfied else "No",
            record.reason,
            str(record.rating),
        ]
    ]

    result = (
        sheets.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=target_range,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            includeValuesInResponse=True,
            responseValueRenderOption="FORMATTED_VALUE",
            body={"values": values},
        )
        .execute()
    )

    updated_rows = (result.get("updates") or {}).get("updatedRows") or 0
    if updated_rows < 1:
        raise RuntimeError(f"Google Sheets append returned no updated rows: {result}")

    log_event(
        "sheets.appended",
        range=target_range,
        updated_rows=updated_rows,
    )

    updated_data = (result.get("updates") or {}).get("updatedData") or {}
    returned_values = updated_data.get("values") or []
    if returned_values and returned_values[0] and len(returned_values[0]) >= 4:
        ticket_number = str(returned_values[0][3]).strip()
        if ticket_number:
            return ticket_number

    return "T-PENDING"


def send_feedback_email(record: FeedbackRecord) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not smtp_host or not smtp_user or not smtp_pass or not smtp_from:
        raise ValueError(
            "Missing SMTP configuration. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM."
        )

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = record.caller_email
    msg["Subject"] = f"Your support feedback receipt ({record.ticket_number})"

    msg.set_content(
        "\n".join(
            [
                f"Hello {record.caller_name},",
                "",
                "Thank you for speaking with our support team today.",
                "Your feedback has been recorded and is important to us.",
                "",
                f"Ticket Number: {record.ticket_number}",
                f"Issue Topic: {record.topic}",
                f"Resolution Satisfaction: {'Yes' if record.satisfied else 'No'}",
                f"Reason: {record.reason}",
                f"Service Rating (1-10): {record.rating}",
                f"Date and Time: {record.created_at}",
                "",
                "We appreciate your time and your voice helps us improve our service.",
                "",
                "Best regards,",
                "Customer Support Team",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    log_event("email.sent", to=record.caller_email)


def store_feedback_and_notify(
    caller_name: str,
    caller_email: str,
    satisfied: bool,
    reason: str,
    rating: int,
    topic: str,
) -> tuple[str, list[str]]:
    ticket_number = "T-PENDING"
    created_at = datetime.now().isoformat(timespec="seconds")
    record = FeedbackRecord(
        caller_name=caller_name,
        caller_email=caller_email,
        satisfied=satisfied,
        reason=reason,
        rating=rating,
        topic=topic,
        ticket_number=ticket_number,
        created_at=created_at,
    )

    errors: list[str] = []

    try:
        ticket_number = append_feedback_to_sheet(record)
        record.ticket_number = ticket_number
    except Exception as e:  # pragma: no cover
        logger.exception("Failed to append feedback to Google Sheets")
        errors.append(f"sheets: {e}")

    try:
        send_feedback_email(record)
    except Exception as e:  # pragma: no cover
        logger.exception("Failed to send feedback confirmation email")
        errors.append(f"email: {e}")

    return ticket_number, errors
