import argparse
from app.services.sheets_archieve_service import save_violations

from apscheduler.schedulers.blocking import BlockingScheduler
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
            return "Не зафиксирован приход"

        if v.type.value == "NO_DEPARTURE":
            return "Нет отметки об уходе"

        if v.type.value == "LATE":
            if v.fact_time and v.plan_time:
                parts.append(
                    f"Опоздание {v.delta_minutes} мин (план {v.plan_time.strftime('%H:%M')}, факт {v.fact_time.strftime('%H:%M')} ) "
                    
                )
            else:
                parts.append(f"Опоздание {v.delta_minutes} мин")

        
        if v.type.value == "EARLY_LEAVE":
            if v.fact_time and v.plan_time:
                parts.append(
                    f"Ранний уход {v.delta_minutes} мин (план {v.plan_time.strftime('%H:%M')}, факт {v.fact_time.strftime('%H:%M')})"
                    
                )
            else:
                parts.append(f"Ранний уход {v.delta_minutes} мин")


    return ", ".join(parts)

def _fmt(t) -> str:
    """Форматирует time или None в строку."""
    return t.strftime("%H:%M") if t else "нб"

def build_telegram_report(target_date: date, violations_by_employee: dict) -> str:
    

    lines = []
    
    lines.append(f"📅 Отчет за: {format_report_date(target_date)}")
    lines.append("")

    total_employees = len(violations_by_employee)
    without_violations = 0

    for employee, violations in violations_by_employee.items():
        if not violations:
            without_violations += 1
            continue

        viol_text = _format_violations(violations)
        lines.append(f"👤 {employee}\n{viol_text}")
        lines.append("")  

   
    if without_violations == total_employees:
        lines.append(f"✅ Нарушений нет")
        lines.append(f"✅ Нарушений не выявлено. Все офлайн-сотрудники ({total_employees} чел.) в норме")
    else:
        lines.append(f" 👥 Без нарушений: {without_violations} человек")

    return "\n".join(lines)

def main():
    violations_by_employee = {}
    
    target: date = get_target_date()
    # target=date(2026, 3, 29)
    # print(f"\n{'='*60}")
    # print(f"  Отчёт за {format_report_date(target)}")
    # print(f"{'='*60}\n")

    #  Загружаем список сотрудников
    employees = load_employees(EMPLOYEES_SHEET_ID)
    logger.info("Сотрудников в списке: %d", len(employees))

    #  Загружаем все записи прихода/ухода за дату одним запросом
    try:
        attendance_map = load_attendance(TIME_SHEET_ID, target)
    except Exception as exc:
        logger.error("Не удалось загрузить таблицу посещаемости: %s", exc)
        attendance_map = {}


# ----------------------------------------------Не забыть отправить Эржану---------------
    has_data = any(
    rec is not None and (rec.arrival is not None or rec.departure is not None)
    for rec in attendance_map.values()
)

    if not attendance_map or not has_data:
        msg = (
        f"Отчет за {format_report_date(target)} не сформирован\n"
        f"Причина: таблица посещаемости не заполнена"
    )
        logger.warning(msg)
        send_message(msg)
        return
# -----------------------------------------------------------------------------------------


    # Заголовок таблицы вывода
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

    #  Перебираем сотрудников
    for emp in employees:
        # Плановое время из ICS 
        try:
            events = get_work_events(emp.ics_url, target)
            planned_arrival, planned_departure = _planned_times(events)
        except Exception as exc:
            logger.warning("Ошибка при загрузке календаря %s: %s", emp.full_name, exc)
            planned_arrival = planned_departure = None

        # Фактическое время из Sheets
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

    # сохранение в архив таблицу
    # all_violations = [v for vlist in violations_by_employee.values() for v in vlist]
    # save_violations(all_violations, target)

    print()

    
def run_scheduler():
    scheduler = BlockingScheduler(timezone="Asia/Bishkek")
    scheduler.add_job(
        main,
        trigger="cron",
        day_of_week="mon-fri",
        hour=13,
        minute=0,
    )
 
    logger.info(
        "Планировщик запущен. Задача: пн–пт в 13:00 (Asia/Bishkek). "
        
    )
 
    scheduler.start()

if __name__ == "__main__":
    main()

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="WorkTimeControl")
#     parser.add_argument(
#         "--now",
#         action="store_true",
#         help="Запустить задачу немедленно (тест) и выйти",
#     )
#     args = parser.parse_args()
 
#     if args.now:
#         main()
#     else:
#         run_scheduler()
 