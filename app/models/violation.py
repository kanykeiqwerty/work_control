from dataclasses import dataclass
from datetime import time
from enum import Enum
from typing import Optional


class ViolationType(str, Enum):
    ABSENT = "ABSENT"          # не пришёл
    LATE = "LATE"              # опоздание
    EARLY_LEAVE = "EARLY_LEAVE" # ранний уход
    NO_DEPARTURE = "NO_DEPARTURE" # нет ухода


@dataclass
class Violation:
    employee: str
    type: ViolationType

    plan_time: Optional[time] = None
    fact_time: Optional[time] = None

    delta_minutes: Optional[int] = None  # разница во времени