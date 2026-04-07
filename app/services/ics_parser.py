from __future__ import annotations

from datetime import date
import logging

from app.utils.ics_utils import (
    EventType,
    WorkEvent,
    _classify,
    _occurs_on,
    _parse_vevent_blocks,
    _is_override_for_date,
    _get_relocated_overrides,
    get_overridden_dates,
)
from .calendar_service import load_ics

logger = logging.getLogger(__name__)


def get_work_events(source: str, target: date) -> list[WorkEvent]:
    
    text = load_ics(source)
    blocks = _parse_vevent_blocks(text)
    results: list[WorkEvent] = []

    # Предварительно собираем переопределённые даты для каждого UID,
    # чтобы не вызывать get_overridden_dates повторно в цикле.
    uid_overrides: dict[str, set] = {}
    for block in blocks:
        uid = block.get("UID", "")
        if uid and "RECURRENCE-ID" in block:
            if uid not in uid_overrides:
                uid_overrides[uid] = get_overridden_dates(blocks, uid)

    # --- Шаг 1: Override-блоки по исходной дате (RECURRENCE-ID.date() == target) ---
    # Собираем UID тех override'ов, которые уже добавили событие на target,
    # чтобы не добавить то же вхождение ещё раз через основную серию.
    overridden_uids_for_target: set[str] = set()

    for block in blocks:
        if "RECURRENCE-ID" not in block:
            continue

        summary = block.get("SUMMARY", "").strip()
        etype = _classify(summary)
        if etype == EventType.IGNORE:
            continue

        override = _is_override_for_date(block, target)
        if override is None:
            continue

        start, end = override

# Запоминаем UID в любом случае — серия не должна генерировать вхождение на эту дату
        uid = block.get("UID", "")
        if uid:
            overridden_uids_for_target.add(uid)

# Событие перенесено на другой день — не показываем за target
        if start.date() != target:
            continue

        results.append(WorkEvent(summary=summary, event_type=etype, start=start, end=end))
    # --- Шаг 2: Перенесённые override-блоки (новая дата == target) ---
    for summary, start, end in _get_relocated_overrides(blocks, target):
        etype = _classify(summary)
        if etype == EventType.IGNORE:
            continue
        results.append(WorkEvent(summary=summary, event_type=etype, start=start, end=end))

    # --- Шаг 3: Основные серии и одиночные события ---
    for block in blocks:
        # Пропускаем override-блоки — они уже обработаны выше
        if "RECURRENCE-ID" in block:
            continue

        summary = block.get("SUMMARY", "").strip()
        etype = _classify(summary)
        if etype == EventType.IGNORE:
            continue

        uid = block.get("UID", "")

        # Если для этого UID уже добавлен override на target — пропускаем
        if uid in overridden_uids_for_target:
            continue

        overridden = uid_overrides.get(uid, set())
        occurrence = _occurs_on(block, target, overridden)
        if occurrence is None:
            continue

        start, end = occurrence
        results.append(WorkEvent(summary=summary, event_type=etype, start=start, end=end))

    results.sort(key=lambda e: e.start)
    return results