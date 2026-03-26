import urllib.request
import urllib.error
import csv
import io
import re
from datetime import date, time
from dataclasses import dataclass
from typing import Optional, Union
import logging
from app.config.settings import TIME_SHEET_ID
from app.models.attendance import AttendanceRecord
# from .config import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.models.employee import Employee
logger = logging.getLogger(__name__)
 
 



   
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
 
 
def _parse_time(cell: str) -> Optional[Union[time, str]]:
    """
    Разбирает время из ячейки таблицы.
    Поддерживает форматы: «10:35», «10:35:00», «10.35»
    Возвращает None если ячейка пустая или не распознана.
    """
    cell = cell.strip().lower()
    if cell in ("", "нб"):
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
 