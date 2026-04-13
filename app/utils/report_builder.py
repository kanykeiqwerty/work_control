import logging
from datetime import date

from app.config.settings import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.services.violation_service import check_violations
from app.services.sheets_employees_service import load_employees
from app.services.sheets_attend_service import load_attendance, get_attendance_for_employee
from app.services.ics_parser import get_work_events
from app.utils.ics_utils import EventType
from app.utils.data_utils import format_report_date

logger = logging.getLogger(__name__)


def _planned_times(events):
    offline = [e for e in events if e.event_type == EventType.OFFLINE]
    if not offline:
        return None, None
    return offline[0].start.time(), offline[-1].end.time()


def _fmt(t) -> str:
    return t.strftime("%H:%M") if t else "нб"

def _collect_violations(target: date) -> list:
    """Собирает сырые объекты нарушений за дату — для сохранения в архив."""
    employees = load_employees(EMPLOYEES_SHEET_ID)
 
    try:
        attendance_map = load_attendance(TIME_SHEET_ID, target)
    except Exception:
        return []
 
    violations_by_employee = {}
 
    for emp in employees:
        try:
            events = get_work_events(emp.ics_url, target)
            planned_arrival, planned_departure = _planned_times(events)
        except Exception:
            planned_arrival = planned_departure = None
 
        rec = get_attendance_for_employee(attendance_map, emp.full_name)
        actual_arrival = rec.arrival if rec else None
        actual_departure = rec.departure if rec else None
 
        if planned_arrival and planned_departure:
            violations = check_violations(
                employee=emp.full_name,
                plan_start=planned_arrival,
                plan_end=planned_departure,
                fact_start=actual_arrival,
                fact_end=actual_departure,
            )
        else:
            violations = []
 
        violations_by_employee[emp.full_name] = violations
 
    return [v for vlist in violations_by_employee.values() for v in vlist]
 

def build_report_data(target_date: date) -> dict | None:
    """
    Собирает данные отчёта за target_date.
    Возвращает dict с полями:
      - date: str
      - employees: list[dict]  — по одному dict на сотрудника
      - summary: dict          — итоговая статистика
    Возвращает None, если таблица посещаемости не заполнена.
    """
    employees = load_employees(EMPLOYEES_SHEET_ID)

    try:
        attendance_map = load_attendance(TIME_SHEET_ID, target_date)
    except Exception as exc:
        logger.error("Не удалось загрузить таблицу посещаемости: %s", exc)
        attendance_map = {}

    has_data = any(
        rec is not None and (rec.arrival is not None or rec.departure is not None)
        for rec in attendance_map.values()
    )

    if not attendance_map or not has_data:
        return None

    result_employees = []

    for emp in employees:
        try:
            events = get_work_events(emp.ics_url, target_date)
            planned_arrival, planned_departure = _planned_times(events)
        except Exception as exc:
            logger.warning("Ошибка при загрузке календаря %s: %s", emp.full_name, exc)
            planned_arrival = planned_departure = None

        rec = get_attendance_for_employee(attendance_map, emp.full_name)
        actual_arrival = rec.arrival if rec else None
        actual_departure = rec.departure if rec else None

        if planned_arrival and planned_departure:
            violations = check_violations(
                employee=emp.full_name,
                plan_start=planned_arrival,
                plan_end=planned_departure,
                fact_start=actual_arrival,
                fact_end=actual_departure,
            )
        else:
            violations = []

        result_employees.append({
            "full_name": emp.full_name,
            "planned_arrival": _fmt(planned_arrival),
            "planned_departure": _fmt(planned_departure),
            "actual_arrival": _fmt(actual_arrival),
            "actual_departure": _fmt(actual_departure),
            "violations": [
                {
                    "type": v.type.value,
                    "delta_minutes": v.delta_minutes,
                    "plan_time": v.plan_time.strftime("%H:%M") if v.plan_time else None,
                    "fact_time": v.fact_time.strftime("%H:%M") if v.fact_time else None,
                }
                for v in violations
            ],
            "violations_raw": violations,
        })

    total = len(result_employees)
    without_violations = sum(1 for e in result_employees if not e["violations"])

    return {
        "date": format_report_date(target_date),
        "date_iso": target_date.isoformat(),
        "employees": result_employees,
        "summary": {
            "total": total,
            "without_violations": without_violations,
            "with_violations": total - without_violations,
        },
    }


def build_telegram_text(report_data: dict) -> str:
    """Форматирует dict отчёта в текст для Telegram."""
    lines = [f"📅 Отчет за: {report_data['date']}", ""]

    for emp in report_data["employees"]:
        violations = emp["violations"]
        if not violations:
            continue

        viol_parts = []
        for v in violations:
            if v["type"] == "ABSENT":
                viol_parts = ["Не зафиксирован приход"]
                break
            if v["type"] == "NO_DEPARTURE":
                viol_parts = ["Нет отметки об уходе"]
                break
            if v["type"] == "LATE":
                if v["plan_time"] and v["fact_time"]:
                    viol_parts.append(
                        f"Опоздание {v['delta_minutes']} мин "
                        f"(план {v['plan_time']}, факт {v['fact_time']})"
                    )
                else:
                    viol_parts.append(f"Опоздание {v['delta_minutes']} мин")
            if v["type"] == "EARLY_LEAVE":
                if v["plan_time"] and v["fact_time"]:
                    viol_parts.append(
                        f"Ранний уход {v['delta_minutes']} мин "
                        f"(план {v['plan_time']}, факт {v['fact_time']})"
                    )
                else:
                    viol_parts.append(f"Ранний уход {v['delta_minutes']} мин")

        lines.append(f"👤 {emp['full_name']}\n{', '.join(viol_parts)}")
        lines.append("")

    s = report_data["summary"]
    if s["with_violations"] == 0:
        lines.append(f"✅ Нарушений не выявлено. Все офлайн-сотрудники ({s['total']} чел.) в норме")
    else:
        lines.append(f"👥 Без нарушений: {s['without_violations']} человек")

    return "\n".join(lines)