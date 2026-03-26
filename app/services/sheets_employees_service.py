

import logging
from app.utils.sheets_utils import _fetch_csv, _normalize_name,_sheet_csv_url
# from config.settings import TIME_SHEET_ID
# from models.attendance import AttendanceRecord
# from .config import EMPLOYEES_SHEET_ID, TIME_SHEET_ID
from app.models.employee import Employee
logger = logging.getLogger(__name__)
 
 




 

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
