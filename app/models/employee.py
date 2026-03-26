from dataclasses import dataclass


@dataclass
class Employee:
    """Запись из справочника сотрудников."""
    number: int       # Порядковый номер
    full_name: str    # ФИО (точно как в таблице приход/уход)
    ics_url: str      # Публичная ICS-ссылка
 
    def __str__(self):
        return f"#{self.number} {self.full_name}"
 