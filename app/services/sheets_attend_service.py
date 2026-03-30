import re
from datetime import date

from typing import Optional
import logging
from app.utils.sheets_utils import _fetch_csv, _normalize_name, _parse_time, _sheet_csv_url
from app.config.settings import TIME_SHEET_ID
from app.models.attendance import AttendanceRecord
# from .config import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.models.employee import Employee
logger = logging.getLogger(__name__)
 
 




def find_date_columns(header_row:list[str], target_date:date)->Optional[tuple[int, int]]:
    date_str=target_date.strftime("%d.%m.%Y")
    return None


def load_attendance(
    spreadsheet_id: str,
    
    target_date: date,
) -> dict[str, AttendanceRecord]:
    
    url = _sheet_csv_url(spreadsheet_id)
    rows = _fetch_csv(url)
 
    if len(rows) < 2:
        raise ValueError("Таблица приход/уход пустая или слишком короткая")
 
    date_str = target_date.strftime("%d.%m.%Y")
    row1 = rows[0]  # Строка 1: даты
    row2 = rows[1]
    row3=rows[2]  # Строка 2: Приход/Уход
 
    
    date_col = None
    for col_idx, cell in enumerate(row1):
        if cell.strip() == date_str:
            date_col = col_idx
            break
 
    if date_col is None:
        logger.warning(f"Дата {date_str} не найдена")
        return {}
 
    
    col_arrival = col_departure = None
    for offset in range(0, min(4, len(row3) - date_col)):
        header = row3[date_col + offset].strip().lower()
        if "вход" in header and col_arrival is None:
            col_arrival = date_col + offset
        elif "выход" in header and col_departure is None:
            col_departure = date_col + offset
 
    if col_arrival is None or col_departure is None:
        raise ValueError(
            f"Не найдены заголовки «Приход»/«Уход» рядом с датой {date_str} "
            f"(проверьте строку 2 таблицы)"
        )
 
    logger.info(
        "Дата %s: колонка прихода=%d, ухода=%d",
        date_str, col_arrival, col_departure,
    )
 
   
    records: dict[str, AttendanceRecord] = {}
    for row in rows[3:]:
        if not row or not row[0].strip():
            continue
 
        full_name = _normalize_name(row[0])
 
        arrival_raw   = row[col_arrival]   if col_arrival   < len(row) else ""
        departure_raw = row[col_departure] if col_departure < len(row) else ""
 
        records[full_name.lower()] = AttendanceRecord(
            full_name=full_name,
            check_date=target_date,
            arrival=_parse_time(arrival_raw),
            departure=_parse_time(departure_raw),
        )
 
    logger.info("Прочитано записей приход/уход: %d", len(records))
    return records
 
 
def get_attendance_for_employee(
    records: dict[str, AttendanceRecord],
    full_name: str,
) -> Optional[AttendanceRecord]:
   
    key = _normalize_name(full_name).lower()
    record = records.get(key)
    if record is None:
        logger.warning("ФИО не найдено в таблице приход/уход: %r", full_name)
    return record


# a=load_attendance(TIME_SHEET_ID, date(2026, 3, 23))
# for i in a.values():
#     print(i)

# b= get_attendance_for_employee(a, "Ашыракманова Каныкей")
# print(b)