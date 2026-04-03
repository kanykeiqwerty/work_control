from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from datetime import date, datetime, timedelta

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    OFFLINE = "offline"  # офлайн — проверяем приход/уход
    ONLINE = "online"  # онлайн  — пропускаем
    IGNORE = "ignore"  # не рабочее — пропускаем


SUMMARY_RULES: list[tuple[str, EventType]] = [
    ("работа (оффлайн)", EventType.OFFLINE),
    ("работа 6 (оффлайн)", EventType.OFFLINE),
    ("работа (офлайн)", EventType.OFFLINE),
    ("работа оффлайн", EventType.OFFLINE),
    ("работа (онлайн)", EventType.ONLINE),
    ("работа онлайн", EventType.ONLINE),
]


@dataclass
class WorkEvent:
    summary: str
    event_type: EventType
    start: datetime  # naive, local time (Asia/Bishkek)
    end: datetime  # naive, local time


BISHKEK_OFFSET = timedelta(hours=6)
BYDAY_MAP = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_dt(value: str, tzid: Optional[str]) -> datetime:
    value = value.strip()
    utc_suffix = value.endswith("Z")
    clean = value.rstrip("Z")

    if len(clean) == 15:
        dt = datetime.strptime(clean, "%Y%m%dT%H%M%S")
    elif len(clean) == 8:
        dt = datetime.strptime(clean, "%Y%m%d")
    else:
        raise ValueError(f"Неизвестный формат даты: {value!r}")

    if utc_suffix:
        dt = dt + BISHKEK_OFFSET

    return dt


def _normalize(text: str) -> str:
    text = text.lower()

    # убрать лишние пробелы
    text = re.sub(r"\s+", " ", text)

    # убрать пробелы вокруг скобок
    text = re.sub(r"\s*\(\s*", "(", text)
    text = re.sub(r"\s*\)\s*", ")", text)

    # унифицировать оффлайн/офлайн
    text = text.replace("оффлайн", "офлайн")

    return text.strip()


def _parse_vevent_blocks(text: str) -> list[dict[str, str]]:
    # Раскрываем line folding
    text = re.sub(r"\r?\n[ \t]", "", text)

    events: list[dict[str, str]] = []
    current: Optional[dict[str, str]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key_full, _, val = line.partition(":")
            key = key_full.split(";")[0].upper()
            current[key] = val
            current[f"_raw_{key}"] = key_full

    return events


def _get_tzid(raw_key: str) -> Optional[str]:
    m = re.search(r"TZID=([^;:]+)", raw_key)
    return m.group(1) if m else None


def _classify(summary: str) -> EventType:
    s = _normalize(summary)

    if "работа" in s and ("офлайн" in s or "оффлайн" in s):
        return EventType.OFFLINE

    if "работа" in s and "онлайн" in s:
        return EventType.ONLINE

    return EventType.IGNORE


def _parse_rrule(rrule_str: str) -> dict[str, str]:
    result = {}
    for part in rrule_str.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.upper()] = v
    return result


def get_overridden_dates(blocks: list[dict], uid: str) -> set[date]:
    """Возвращает даты, для которых есть override для данного UID."""
    overridden = set()
    for b in blocks:
        if b.get("UID") == uid and "RECURRENCE-ID" in b:
            raw = b.get("_raw_RECURRENCE-ID", "RECURRENCE-ID")
            tzid = _get_tzid(raw)
            try:
                dt = _parse_dt(b["RECURRENCE-ID"], tzid)
                overridden.add(dt.date())
            except (KeyError, ValueError):
                pass
    return overridden


def _occurs_on(event: dict[str, str], target: date, overridden_dates: set = None) -> Optional[
    tuple[datetime, datetime]]:
    raw_start = event.get("_raw_DTSTART", "DTSTART")
    tzid = _get_tzid(raw_start)

    try:
        dt_start = _parse_dt(event["DTSTART"], tzid)
        dt_end = _parse_dt(event["DTEND"], tzid)
    except (KeyError, ValueError) as e:
        logger.warning(f"Не удалось распарсить время события: {e}")
        return None

    duration = dt_end - dt_start
    rrule_str = event.get("RRULE")

    if rrule_str:
        rrule = _parse_rrule(rrule_str)
        freq = rrule.get("FREQ", "")

        if freq == "WEEKLY":
            byday_raw = rrule.get("BYDAY", "")
            byday_days = {d.strip() for d in byday_raw.split(",")}
            target_byday = {k for k, v in BYDAY_MAP.items() if v == target.weekday()}

            if not byday_days & target_byday:
                return None

            occurrence_start = datetime(
                target.year, target.month, target.day,
                dt_start.hour, dt_start.minute, dt_start.second
            )

            if occurrence_start.date() < dt_start.date():
                return None

            if overridden_dates and occurrence_start.date() in overridden_dates:
                return None

            until_str = rrule.get("UNTIL")
            if until_str:
                try:
                    until_dt = _parse_dt(until_str, tzid)
                    if occurrence_start > until_dt:
                        return None
                except ValueError:
                    pass

            count_str = rrule.get("COUNT")
            if count_str:
                try:
                    count = int(count_str)
                    weeks_since = (target - dt_start.date()).days // 7
                    if weeks_since >= count:
                        return None
                except ValueError:
                    pass

            return occurrence_start, occurrence_start + duration

        # Другие FREQ — проверяем дату напрямую
        if dt_start.date() == target:
            return dt_start, dt_end
        return None

    else:
        if dt_start.date() == target:
            return dt_start, dt_end
        return None


def _is_override_for_date(event: dict[str, str], target: date) -> Optional[tuple[datetime, datetime]]:
    if "RECURRENCE-ID" not in event:
        return None

    raw = event.get("_raw_RECURRENCE-ID", "RECURRENCE-ID")
    tzid = _get_tzid(raw)

    try:
        recur_dt = _parse_dt(event["RECURRENCE-ID"], tzid)
        dt_start = _parse_dt(event["DTSTART"], tzid)
        dt_end = _parse_dt(event["DTEND"], tzid)
    except (KeyError, ValueError):
        return None

    if recur_dt.date() == target:
        return dt_start, dt_end

    return None