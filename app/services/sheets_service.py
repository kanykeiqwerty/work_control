import urllib.request
import urllib.error
import csv
import io
import re
from datetime import date, time
from dataclasses import dataclass
from typing import Optional
import logging
from config import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
 
logger = logging.getLogger(__name__)
 
 

@dataclass
class Employee:
    """Запись из справочника сотрудников."""
    number: int       # Порядковый номер
    full_name: str    # ФИО (точно как в таблице приход/уход)
    ics_url: str      # Публичная ICS-ссылка
 
    def __str__(self):
        return f"#{self.number} {self.full_name}"
 
@dataclass
class AttendanceRecord:
    """Фактические данные прихода/ухода одного сотрудника за один день."""
    full_name: str
    check_date: date
    arrival: Optional[time]     # None = ячейка пустая
    departure: Optional[time]   # None = ячейка пустая
 
    @property
    def arrived(self) -> bool:
        return self.arrival is not None
 
    @property
    def departed(self) -> bool:
        return self.departure is not None
 
    def __str__(self):
        arr = self.arrival.strftime("%H:%M")   if self.arrival   else "—"
        dep = self.departure.strftime("%H:%M") if self.departure else "—"
        return f"{self.full_name}: приход {arr}, уход {dep}"
  

   
def _sheet_csv_url(spreadsheet_id: str) -> str:
    """Формирует URL для CSV-экспорта листа Google Таблицы."""
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid=0"
    )
 
 
def _fetch_csv(url: str, timeout: int = 15) -> list[list[str]]:
   
    logger.info("Загружаем CSV: %s", url[:90])
    req = urllib.request.Request(url, headers={"User-Agent": "WorkTimeControl/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8-sig", errors="replace")  # utf-8-sig снимает BOM
 
    reader = csv.reader(io.StringIO(raw))
    rows = [row for row in reader]
    logger.info("CSV загружен: %d строк", len(rows))
    return rows
 
 
def _parse_time(cell: str) -> Optional[time]:
    """
    Разбирает время из ячейки таблицы.
    Поддерживает форматы: «10:35», «10:35:00», «10.35»
    Возвращает None если ячейка пустая или не распознана.
    """
    cell = cell.strip()
    if not cell:
        return None
 
    m = re.fullmatch(r'(\d{1,2})[:\.](\d{2})(?::\d{2})?', cell)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return time(h, mn)
 
    logger.warning("Не удалось разобрать время: %r", cell)
    return None
 
 
def _normalize_name(name: str) -> str:
    """Нормализует ФИО: убирает лишние пробелы, приводит к нижнему регистру для сравнения."""
    return " ".join(name.strip().split())
 
 

def load_employees(spreadsheet_id: str) -> list[Employee]:
   
    url = _sheet_csv_url(spreadsheet_id)
    rows = _fetch_csv(url)
 
    employees = []
    for i, row in enumerate(rows):
        # Пропускаем заголовок и пустые строки
        if i == 0:
            continue
        if len(row) < 3 or not row[1].strip():
            continue
 
        num_str = row[0].strip()
        full_name = _normalize_name(row[1])
        ics_url = row[2].strip()
 
        if not ics_url or not full_name:
            logger.warning("Строка %d: пропущена (пустое ФИО или ICS-ссылка)", i + 1)
            continue
 
        # try:
        #     number = int(num_str) if num_str.isdigit() else i
        # except ValueError:
        #     number = i
 
        employees.append(Employee(number=num_str, full_name=full_name, ics_url=ics_url))
 
    logger.info("Загружено сотрудников: %d", len(employees))
    return employees
 
# a=load_employees(EMPLOYEES_SHEET_ID)
# for i in a:
#     print(i.full_name, i.ics_url)


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
        raise ValueError(
            f"Дата {date_str} не найдена в строке 1 таблицы приход/уход. "
            f"Доступные даты: {[c for c in row1 if re.match(r'\d{2}\.\d{2}\.\d{4}', c.strip())]}"
        )
 
    
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


a=load_attendance(TIME_SHEET_ID, date(2026, 3, 23))
for i in a:
    print()