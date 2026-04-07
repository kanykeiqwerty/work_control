from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from datetime import date, datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    OFFLINE = "offline"   # офлайн — проверяем приход/уход
    ONLINE  = "online"    # онлайн  — пропускаем
    IGNORE  = "ignore"    # не рабочее — пропускаем


@dataclass
class WorkEvent:
    summary:    str
    event_type: EventType
    start:      datetime   # naive, local time (Asia/Bishkek)
    end:        datetime   # naive, local time


BISHKEK_OFFSET = timedelta(hours=6)
BYDAY_MAP = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_dt(value: str, tzid: Optional[str]) -> datetime:
    """
    Парсит строку даты/времени из ICS в naive datetime в локальном времени Бишкека.

    Поддерживает:
      - "20260406T130000Z"   — UTC, конвертируем прибавляя +6
      - "20260406T130000"    — уже локальное время (TZID=Asia/Bishkek)
      - "20260406"           — только дата (VALUE=DATE)
    """
    value = value.strip()
    utc_suffix = value.endswith("Z")
    clean = value.rstrip("Z")

    if len(clean) == 15:          # YYYYMMDDTHHmmss
        dt = datetime.strptime(clean, "%Y%m%dT%H%M%S")
    elif len(clean) == 8:         # YYYYMMDD
        dt = datetime.strptime(clean, "%Y%m%d")
    else:
        raise ValueError(f"Неизвестный формат даты: {value!r}")

    if utc_suffix:
        dt = dt + BISHKEK_OFFSET

    return dt


def _normalize(text: str) -> str:
    """Приводит строку к нижнему регистру, убирает лишние пробелы и скобки."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\(\s*", "(", text)
    text = re.sub(r"\s*\)\s*", ")", text)
    text = text.replace("оффлайн", "офлайн")
    return text.strip()


def _classify(summary: str) -> EventType:
    """Определяет тип события по названию."""
    s = _normalize(summary)

    if "работа" in s and ("офлайн" in s or "оффлайн" in s):
        return EventType.OFFLINE

    if "работа" in s and "онлайн" in s:
        return EventType.ONLINE

    return EventType.IGNORE


def _get_tzid(raw_key: str) -> Optional[str]:
    """Извлекает TZID из строки вида 'DTSTART;TZID=Asia/Bishkek'."""
    m = re.search(r"TZID=([^;:]+)", raw_key)
    return m.group(1) if m else None


def _parse_vevent_blocks(text: str) -> list[dict]:
    """
    Разбирает ICS-текст и возвращает список словарей для каждого VEVENT.

    Особенности:
    - Раскрывает line folding (строки, продолжающиеся с пробела/таба).
    - Поле EXDATE может встречаться несколько раз в одном блоке —
      сохраняется как список под ключом "_EXDATES".
    - Для каждого поля дополнительно хранится "_raw_<KEY>" — полная строка
      до ':' (нужна для извлечения TZID).
    """
    # Раскрываем line folding: \r\n или \n + пробел/таб → продолжение строки
    text = re.sub(r"\r?\n[ \t]", "", text)

    events: list[dict] = []
    current: Optional[dict] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line == "BEGIN:VEVENT":
            current = {"_EXDATES": [], "_EXDATE_TZIDS": []}
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key_full, _, val = line.partition(":")
            key = key_full.split(";")[0].upper()

            if key == "EXDATE":
                # Несколько EXDATE в одном блоке — собираем в список
                current["_EXDATES"].append(val)
                current["_EXDATE_TZIDS"].append(key_full)  # для TZID
            else:
                current[key] = val
                current[f"_raw_{key}"] = key_full

    return events


def _parse_rrule(rrule_str: str) -> dict[str, str]:
    """Разбирает строку RRULE в словарь."""
    result = {}
    for part in rrule_str.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.upper()] = v
    return result


def _is_exdate(event: dict, target: date) -> bool:
    """
    Возвращает True, если target является исключённой датой (EXDATE) события.
    Корректно обрабатывает несколько строк EXDATE в одном блоке.
    """
    exdates = event.get("_EXDATES", [])
    exdate_tzids = event.get("_EXDATE_TZIDS", [])

    for i, exdate_val in enumerate(exdates):
        raw_key = exdate_tzids[i] if i < len(exdate_tzids) else "EXDATE"
        tzid = _get_tzid(raw_key)
        try:
            exdate_dt = _parse_dt(exdate_val, tzid)
            if exdate_dt.date() == target:
                return True
        except ValueError:
            pass

    return False


def get_overridden_dates(blocks: list[dict], uid: str) -> set[date]:
    """
    Возвращает множество дат (по RECURRENCE-ID), для которых существует
    override-блок для данного UID. Эти даты нужно пропускать в основной серии.
    """
    overridden: set[date] = set()
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


def _occurs_on(
    event: dict,
    target: date,
    overridden_dates: Optional[set] = None,
) -> Optional[tuple[datetime, datetime]]:
    """
    Проверяет, попадает ли событие на дату target.

    Учитывает:
    - Одиночные события (без RRULE)
    - Еженедельные повторения (RRULE:FREQ=WEEKLY)
    - UNTIL и COUNT ограничения
    - EXDATE — исключённые даты
    - overridden_dates — даты, переопределённые отдельным блоком RECURRENCE-ID

    Возвращает (start, end) если событие происходит, иначе None.
    """
    raw_start = event.get("_raw_DTSTART", "DTSTART")
    tzid = _get_tzid(raw_start)

    try:
        dt_start = _parse_dt(event["DTSTART"], tzid)
        dt_end   = _parse_dt(event["DTEND"], tzid)
    except (KeyError, ValueError) as e:
        logger.warning("Не удалось распарсить время события: %s", e)
        return None

    duration  = dt_end - dt_start
    rrule_str = event.get("RRULE")

    if rrule_str:
        rrule = _parse_rrule(rrule_str)
        freq  = rrule.get("FREQ", "")

        if freq == "WEEKLY":
            byday_raw  = rrule.get("BYDAY", "")
            byday_days = {d.strip() for d in byday_raw.split(",") if d.strip()}
            target_byday = {k for k, v in BYDAY_MAP.items() if v == target.weekday()}

            # День недели не совпадает
            if not byday_days & target_byday:
                return None

            occurrence_start = datetime(
                target.year, target.month, target.day,
                dt_start.hour, dt_start.minute, dt_start.second,
            )

            # Дата раньше начала серии
            if occurrence_start.date() < dt_start.date():
                return None

            # Дата переопределена отдельным override-блоком
            if overridden_dates and occurrence_start.date() in overridden_dates:
                return None

            # Дата исключена через EXDATE
            if _is_exdate(event, target):
                return None

            # Проверка UNTIL
            until_str = rrule.get("UNTIL")
            if until_str:
                try:
                    until_dt = _parse_dt(until_str, tzid)
                    if occurrence_start > until_dt:
                        return None
                except ValueError:
                    pass

            # Проверка COUNT
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

        # Другие FREQ (DAILY, MONTHLY и т.д.) — проверяем дату напрямую
        if dt_start.date() == target:
            return dt_start, dt_end
        return None

    else:
        # Одиночное событие без RRULE
        if dt_start.date() == target:
            return dt_start, dt_end
        return None


def _is_override_for_date(
    event: dict,
    target: date,
) -> Optional[tuple[datetime, datetime]]:
    """
    Проверяет, является ли блок override'ом (имеет RECURRENCE-ID)
    для даты target.

    Логика:
    - RECURRENCE-ID содержит исходную дату вхождения серии (которую заменяем).
    - DTSTART содержит новую дату/время (может быть перенесено на другой день).
    - Возвращаем (DTSTART, DTEND) если RECURRENCE-ID.date() == target,
      то есть ищем override по исходной дате.

    Отдельно: если событие перенесено на другую дату (DTSTART.date() != target),
    оно будет возвращено с новым временем, но идентифицировано по старой дате.
    Это стандартное поведение RFC 5545.
    """
    if "RECURRENCE-ID" not in event:
        return None

    raw = event.get("_raw_RECURRENCE-ID", "RECURRENCE-ID")
    tzid = _get_tzid(raw)

    try:
        recur_dt = _parse_dt(event["RECURRENCE-ID"], tzid)
        dt_start = _parse_dt(event["DTSTART"], tzid)
        dt_end   = _parse_dt(event["DTEND"], tzid)
    except (KeyError, ValueError):
        return None

    if recur_dt.date() == target:
        return dt_start, dt_end

    return None


def _get_relocated_overrides(
    blocks: list[dict],
    target: date,
) -> list[tuple[str, datetime, datetime]]:
    """
    Возвращает список (summary, start, end) для override-событий,
    которые были ПЕРЕНЕСЕНЫ на дату target (DTSTART.date() == target,
    но RECURRENCE-ID.date() != target).

    Это нужно для случаев, когда сотрудник, например, работал 2 апреля
    вместо 30 марта — событие есть в календаре, но не попадёт ни через
    основную серию, ни через _is_override_for_date(target=2 апреля).
    """
    results = []
    for block in blocks:
        if "RECURRENCE-ID" not in block:
            continue

        raw_recur = block.get("_raw_RECURRENCE-ID", "RECURRENCE-ID")
        tzid_recur = _get_tzid(raw_recur)
        raw_start = block.get("_raw_DTSTART", "DTSTART")
        tzid_start = _get_tzid(raw_start)

        try:
            recur_dt = _parse_dt(block["RECURRENCE-ID"], tzid_recur)
            dt_start = _parse_dt(block["DTSTART"], tzid_start)
            dt_end   = _parse_dt(block["DTEND"], tzid_start)
        except (KeyError, ValueError):
            continue

        # Перенесённое событие: исходная дата НЕ совпадает с target,
        # но новая дата (DTSTART) совпадает с target
        if recur_dt.date() != target and dt_start.date() == target:
            summary = block.get("SUMMARY", "").strip()
            results.append((summary, dt_start, dt_end))

    return results