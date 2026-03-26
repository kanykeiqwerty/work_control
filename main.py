"""
main.py — точка входа.

Для каждого сотрудника:
  1. Загружает его ICS-календарь и находит плановое время прихода/ухода
     за целевую дату (get_target_date).
  2. Ищет фактическое время прихода/ухода в Google Sheets (TIME_SHEET_ID).
  3. Выводит ФИО, плановое и фактическое время.
"""

import logging
from datetime import date

from app.config.settings import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.services.violation_service import check_violations
from app.utils.data_utils import get_target_date, format_report_date
from app.services.sheets_employees_service import load_employees
from app.services.sheets_attend_service import load_attendance, get_attendance_for_employee
from app.services.ics_parser import get_work_events
from app.utils.ics_utils import EventType
from app.services.telegram_service import send_message

from decouple import config

BOT_TOKEN=config('BOT_TOKEN')
CHAT_ID=config('CHAT_ID')

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def _planned_times(events):
    """
    Возвращает (planned_arrival, planned_departure) из списка WorkEvent,
    рассматривая только OFFLINE-блоки.
    Если офлайн-блоков нет — возвращает (None, None).
    """
    offline = [e for e in events if e.event_type == EventType.OFFLINE]
    if not offline:
        return None, None
    return offline[0].start.time(), offline[-1].end.time()

def _format_violations(violations) -> str:
    if not violations:
        return "OK"

    parts = []

    for v in violations:
        if v.type.value == "ABSENT":
            return "Не пришёл"

        if v.type.value == "NO_DEPARTURE":
            return "Нет выхода"

        if v.type.value == "LATE":
            parts.append(f"Опоздание +{v.delta_minutes}м")

        if v.type.value == "EARLY_LEAVE":
            parts.append(f"Ранний уход -{v.delta_minutes}м")

    return ", ".join(parts)

def _fmt(t) -> str:
    """Форматирует time или None в строку."""
    return t.strftime("%H:%M") if t else "нб"

def build_telegram_report(target_date: date, violations_by_employee: dict) -> str:
    today = date.today()

    lines = []
    lines.append(f"📊 Отчёт сформирован: {today.strftime('%d.%m.%Y')}")
    lines.append(f"📅 Дата проверки: {target_date.strftime('%d.%m.%Y')}")
    lines.append("")

    for employee, violations in violations_by_employee.items():
        if not violations:
            continue

        viol_text = _format_violations(violations)
        lines.append(f"👤 {employee} — {viol_text}")

    if len(lines) == 3:
        lines.append("✅ Нарушений нет")

    return "\n".join(lines)

def main():
    violations_by_employee = {}
    
    # target: date = get_target_date()
    target=date(2026, 3, 24)
    print(f"\n{'='*60}")
    print(f"  Отчёт за {format_report_date(target)}")
    print(f"{'='*60}\n")

    # 1. Загружаем список сотрудников
    employees = load_employees(EMPLOYEES_SHEET_ID)
    logger.info("Сотрудников в списке: %d", len(employees))

    # 2. Загружаем все записи прихода/ухода за дату одним запросом
    try:
        attendance_map = load_attendance(TIME_SHEET_ID, target)
    except ValueError as exc:
        logger.error("Не удалось загрузить таблицу посещаемости: %s", exc)
        attendance_map = {}

    # 3. Заголовок таблицы вывода
    col = "{:<35} {:>10} {:>10} {:>12} {:>12} {:>30}"
    header = col.format(
    "ФИО",
    "Пл.приход",
    "Пл.уход",
    "Факт.приход",
    "Факт.уход",
    "Нарушение"
)
    print(header)
    print("-" * len(header))

    # 4. Перебираем сотрудников
    for emp in employees:
        # --- Плановое время из ICS ---
        try:
            events = get_work_events(emp.ics_url, target)
            planned_arrival, planned_departure = _planned_times(events)
        except Exception as exc:
            logger.warning("Ошибка при загрузке календаря %s: %s", emp.full_name, exc)
            planned_arrival = planned_departure = None

        # --- Фактическое время из Sheets ---
        rec = get_attendance_for_employee(attendance_map, emp.full_name)
        actual_arrival   = rec.arrival   if rec else None
        actual_departure = rec.departure if rec else None


        
        violations: list = []
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
        viol_str = _format_violations(violations)

        print(col.format(
            emp.full_name[:34],
            _fmt(planned_arrival),
            _fmt(planned_departure),
            _fmt(actual_arrival),
            _fmt(actual_departure),
            viol_str
        ))
    message = build_telegram_report(target, violations_by_employee)
    send_message(message)

    print()


if __name__ == "__main__":
    main()