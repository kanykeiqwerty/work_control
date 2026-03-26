from datetime import date, time
from dataclasses import dataclass
from typing import Optional, Union


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
        arr = self.arrival.strftime("%H:%M")   if self.arrival   else "нб"
        dep = self.departure.strftime("%H:%M") if self.departure else "нб"
        return f"{self.full_name}: приход {arr}, уход {dep}"
  