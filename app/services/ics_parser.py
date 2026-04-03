
from __future__ import annotations


from datetime import date


import logging
from app.utils.ics_utils import EventType, WorkEvent, _classify, _occurs_on, _parse_vevent_blocks, _is_override_for_date, get_overridden_dates
from .calendar_service import load_ics

logger = logging.getLogger(__name__)


def get_work_events(source: str, target: date) -> list[WorkEvent]:
    text = load_ics(source)
    blocks = _parse_vevent_blocks(text)
    results: list[WorkEvent] = []

    
    uid_overrides: dict[str, set] = {}
    for block in blocks:
        uid = block.get("UID", "")
        if uid and "RECURRENCE-ID" in block:
            uid_overrides.setdefault(uid, set())
            uid_overrides[uid] |= get_overridden_dates(blocks, uid)

    for block in blocks:
        summary = block.get("SUMMARY", "").strip()
        etype = _classify(summary)
        if etype == EventType.IGNORE:
            continue

        uid = block.get("UID", "")

        
        override = _is_override_for_date(block, target)
        if override:
            start, end = override
            results.append(WorkEvent(summary=summary, event_type=etype, start=start, end=end))
            continue

        
        overridden = uid_overrides.get(uid, set())
        occurrence = _occurs_on(block, target, overridden)
        if occurrence is None:
            continue

        start, end = occurrence
        results.append(WorkEvent(summary=summary, event_type=etype, start=start, end=end))

    results.sort(key=lambda e: e.start)
    return results

