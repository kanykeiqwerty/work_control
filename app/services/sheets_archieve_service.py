"""
sheets_archive_service.py — запись нарушений в архив Google Sheets.
"""

import logging
from datetime import date
from typing import Optional

import requests
from google.oauth2 import service_account
import google.auth.transport.requests

from app.models.violation import Violation, ViolationType
from app.config.settings import ARCHIEVE_SHEET_ID

logger = logging.getLogger(__name__)

_CREDENTIALS_PATH = "credentials.json"
_SHEET_NAME       = "Лист1"  

_VIOLATION_LABELS = {
    ViolationType.ABSENT:       "Не зафиксирован приход",
    ViolationType.LATE:         "Опоздание",
    ViolationType.EARLY_LEAVE:  "Ранний уход",
    ViolationType.NO_DEPARTURE: "Нет отметки об уходе",
}


def _get_access_token() -> str:
    creds = service_account.Credentials.from_service_account_file(
        _CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _fmt_time(t) -> str:
    return t.strftime("%H:%M") if t else ""


def _violation_to_row(v: Violation, check_date: date) -> list[str]:
    return [
        check_date.strftime("%d.%m.%Y"),
        v.employee,
        _VIOLATION_LABELS.get(v.type, v.type.value),
        _fmt_time(v.plan_time),
        _fmt_time(v.fact_time),
        str(v.delta_minutes) if v.delta_minutes is not None else "",
    ]


def save_violations(violations: list[Violation], check_date: Optional[date] = None) -> None:
    if not violations:
        logger.info("Нарушений нет — ничего не записываем в архив.")
        return

    if check_date is None:
        check_date = date.today()

    rows = [_violation_to_row(v, check_date) for v in violations]
    token = _get_access_token()

    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets"
        f"/{ARCHIEVE_SHEET_ID}/values/{_SHEET_NAME}!A:F:append"
    )

    resp = requests.post(
        url,
        params={
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS",
        },
        json={"values": rows},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )

    resp.raise_for_status()
    updated = resp.json().get("updates", {}).get("updatedRows", len(rows))
    logger.info("Архив: записано %d строк за %s", updated, check_date.strftime("%d.%m.%Y"))