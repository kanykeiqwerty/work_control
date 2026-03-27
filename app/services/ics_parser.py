"""
Шаг 2 — Парсинг ICS
=====================
Парсит ICS-файл (локальный или по URL) и возвращает рабочие события
за конкретную дату.

Классификация событий (настраивается через SUMMARY_RULES):
  - «Рабочее время»  → OFFLINE  (проверяем приход/уход)
  - «Онлайн»         → ONLINE   (пропускаем)
  - всё остальное    → IGNORE

Особенности:
  - Парсинг без внешних библиотек (только stdlib)
  - Поддержка RRULE FREQ=WEEKLY;BYDAY=... (еженедельные повторы)
  - Часовой пояс Asia/Bishkek (UTC+6) — даты приводятся к local naive
  - Поддержка двух форматов DTSTART: с TZID и без (UTC Z)
"""

from __future__ import annotations


from datetime import date


import logging
from app.utils.ics_utils import EventType, WorkEvent, _classify, _occurs_on, _parse_vevent_blocks
from .calendar_service import load_ics

logger = logging.getLogger(__name__)


def get_work_events(source: str, target: date) -> list[WorkEvent]:
    
    text   = load_ics(source)
    blocks = _parse_vevent_blocks(text)

    results: list[WorkEvent] = []

    for block in blocks:
        summary = block.get("SUMMARY", "").strip()
        etype   = _classify(summary)

        if etype == EventType.IGNORE:
            logger.debug(f"  Пропускаем «{summary}» (IGNORE)")
            continue

        occurrence = _occurs_on(block, target)
        if occurrence is None:
            continue

        start, end = occurrence
        results.append(WorkEvent(
            summary=summary,
            event_type=etype,
            start=start,
            end=end,
        ))

    results.sort(key=lambda e: e.start)
    return results

# def describe_day(events: List[WorkEvent]) -> str:
#     """
#     Возвращает текстовое описание дня (офлайн/онлайн события)
#     """
#     if not events:
#         return "нет рабочих событий (выходной / отпуск)"

#     offline = [e for e in events if e.event_type == EventType.OFFLINE]
#     online  = [e for e in events if e.event_type == EventType.ONLINE]

#     if not offline:
#         return f"онлайн-день ({len(online)} событий) — пропускаем"

#     arrival   = offline[0].start
#     departure = offline[-1].end
#     parts = [f"офлайн {len(offline)} блок(а): приход {arrival.strftime('%H:%M')}, уход {departure.strftime('%H:%M')}"]
#     if online:
#         parts.append(f"+ онлайн {len(online)} блок(а)")
#     return ", ".join(parts)

# def describe_day(events: list[WorkEvent]) -> str:
    
#     if not events:
#         return "нет рабочих событий (выходной / отпуск)"

#     offline = [e for e in events if e.event_type == EventType.OFFLINE]
#     online  = [e for e in events if e.event_type == EventType.ONLINE]

#     if not offline:
#         return f"онлайн-день ({len(online)} событий) — пропускаем"

#     arrival   = offline[0].start
#     departure = offline[-1].end
#     parts = [f"офлайн {len(offline)} блок(а): приход {arrival.strftime('%H:%M')}, уход {departure.strftime('%H:%M')}"]
#     if online:
#         parts.append(f"+ онлайн {len(online)} блок(а)")
#     return ", ".join(parts)


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

#     ICS_PATH = "https://calendar.google.com/calendar/ical/kanykeiash5%40gmail.com/public/basic.ics"

#     week_monday = date(2026, 3, 23)
#     day_names   = ["Пн", "Вт", "Ср", "Чт", "Пт"]

#     print("\n" + "="*55)
#     print("  Проверка недели 23.03 – 27.03.2026")
#     print("="*55)

#     for i in range(5):
#         day    = week_monday + timedelta(days=i)
#         events = get_work_events(ICS_PATH, day)
#         print(f"\n{day.strftime('%d.%m.%Y')} ({day_names[i]}):")
#         print(f"  → {describe_day(events)}")
#         for e in events:
#             print(f"     [{e.event_type.value:7}] «{e.summary}»  {e.start.strftime('%H:%M')}–{e.end.strftime('%H:%M')}")

#     print("\n" + "="*55)