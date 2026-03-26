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
from app.utils.data_utils import get_target_date, format_report_date
from app.services.sheets_employees_service import load_employees
from app.services.sheets_attend_service import load_attendance, get_attendance_for_employee
from app.services.ics_parser import get_work_events
from app.utils.ics_utils import EventType

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


def _fmt(t) -> str:
    """Форматирует time или None в строку."""
    return t.strftime("%H:%M") if t else "нб"


def main():
    # target: date = get_target_date()
    print(f"\n{'='*60}")
    print(f"  Отчёт за {format_report_date(date(2026, 3, 23))}")
    print(f"{'='*60}\n")

    # 1. Загружаем список сотрудников
    employees = load_employees(EMPLOYEES_SHEET_ID)
    logger.info("Сотрудников в списке: %d", len(employees))

    # 2. Загружаем все записи прихода/ухода за дату одним запросом
    try:
        attendance_map = load_attendance(TIME_SHEET_ID, date(2026, 3, 23))
    except ValueError as exc:
        logger.error("Не удалось загрузить таблицу посещаемости: %s", exc)
        attendance_map = {}

    # 3. Заголовок таблицы вывода
    col = "{:<35} {:>10} {:>10} {:>12} {:>12}"
    header = col.format("ФИО", "Пл.приход", "Пл.уход", "Факт.приход", "Факт.уход")
    print(header)
    print("-" * len(header))

    # 4. Перебираем сотрудников
    for emp in employees:
        # --- Плановое время из ICS ---
        try:
            events = get_work_events(emp.ics_url, date(2026, 3, 23))
            planned_arrival, planned_departure = _planned_times(events)
        except Exception as exc:
            logger.warning("Ошибка при загрузке календаря %s: %s", emp.full_name, exc)
            planned_arrival = planned_departure = None

        # --- Фактическое время из Sheets ---
        rec = get_attendance_for_employee(attendance_map, emp.full_name)
        actual_arrival   = rec.arrival   if rec else None
        actual_departure = rec.departure if rec else None

        print(col.format(
            emp.full_name[:34],
            _fmt(planned_arrival),
            _fmt(planned_departure),
            _fmt(actual_arrival),
            _fmt(actual_departure),
        ))

    print()


if __name__ == "__main__":
    main()