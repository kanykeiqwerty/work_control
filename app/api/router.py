from fastapi import APIRouter, HTTPException, Query
from datetime import date

from app.config.settings import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.services.violation_service import check_violations
from app.services.sheets_employees_service import load_employees
from app.services.sheets_attend_service import load_attendance, get_attendance_for_employee
from app.services.ics_parser import get_work_events
from app.utils.ics_utils import EventType
from app.utils.data_utils import format_report_date
from app.utils.report_builder import build_report_data

router = APIRouter()


@router.get("/report")
def get_report(target_date: date = Query(..., description="Дата в формате YYYY-MM-DD")):
    """
    Возвращает отчёт о нарушениях за указанную дату.
    Пример: GET /report?target_date=2026-04-08
    """
    try:
        report = build_report_data(target_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Данные посещаемости за {target_date} не найдены или таблица не заполнена",
        )

    return report