from datetime import datetime, time
from typing import List, Optional

from app.models.violation import Violation, ViolationType


def _to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _diff_minutes(t1: time, t2: time) -> int:
    """t1 - t2"""
    return _to_minutes(t1) - _to_minutes(t2)


def check_violations(
    employee: str,
    plan_start: time,
    plan_end: time,
    fact_start: Optional[time],
    fact_end: Optional[time],
) -> List[Violation]:

    violations: List[Violation] = []

    # ❌ 1. Не пришёл
    if fact_start is None and fact_end is None:
        violations.append(
            Violation(
                employee=employee,
                type=ViolationType.ABSENT
            )
        )
        return violations  # дальше смысла нет

    # ❌ 2. Нет ухода
    if fact_start is not None and fact_end is None:
        violations.append(
            Violation(
                employee=employee,
                type=ViolationType.NO_DEPARTURE,
                plan_time=plan_end,
                fact_time=None
            )
        )

    # ❌ 3. Опоздание
    if fact_start is not None:
        delta_start = _diff_minutes(fact_start, plan_start)

        if delta_start > 0:
            violations.append(
                Violation(
                    employee=employee,
                    type=ViolationType.LATE,
                    plan_time=plan_start,
                    fact_time=fact_start,
                    delta_minutes=delta_start
                )
            )

    # ❌ 4. Ранний уход
    if fact_end is not None:
        delta_end = _diff_minutes(plan_end, fact_end)

        if delta_end > 0:
            violations.append(
                Violation(
                    employee=employee,
                    type=ViolationType.EARLY_LEAVE,
                    plan_time=plan_end,
                    fact_time=fact_end,
                    delta_minutes=delta_end
                )
            )

    return violations


# violations = check_violations(
#     employee="Ivan Ivanov",
#     plan_start=time(9, 0),
#     plan_end=time(18, 0),
#     fact_start=time(9, 30),
#     fact_end=time(17, 0),
# )
# print(violations)