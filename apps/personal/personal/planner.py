"""FIXTURE planner — deterministic slot finder, NOT the dossier's AI planner.

The blueprint's bounded-AI proposer + deterministic solver is another seat's
(or a later iteration's) work. This module exists so the personal surface can
demonstrate an exact private plan, approvals, and per-audience previews today.
It never sees network, models, or real data; every output is labeled fixture.
"""
from datetime import datetime, timedelta


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def find_slot(busy: tuple[tuple[str, str], ...], duration_minutes: int,
              day: str = "2026-10-19") -> dict:
    """First free slot of duration_minutes inside 09:00–18:00 avoiding busy."""
    start = datetime.fromisoformat(f"{day}T09:00:00")
    end = datetime.fromisoformat(f"{day}T18:00:00")
    need = timedelta(minutes=duration_minutes)
    intervals = sorted((_parse(s), _parse(e)) for s, e in busy)
    cursor = start
    for b_start, b_end in intervals:
        if cursor + need <= b_start:
            return {"slot_start": cursor.isoformat(), "slot_end": (cursor + need).isoformat(),
                    "planner": "fixture-deterministic"}
        cursor = max(cursor, b_end)
    if cursor + need <= end:
        return {"slot_start": cursor.isoformat(), "slot_end": (cursor + need).isoformat(),
                "planner": "fixture-deterministic"}
    return {"slot_start": None, "slot_end": None, "planner": "fixture-deterministic",
            "note": "no free slot in 09:00-18:00"}


def build_day_plan(calendar, owner: str, call_minutes: int = 20) -> dict:
    """Private day plan: busy intervals + proposed call slot. Fixture-grade."""
    busy = calendar.busy_intervals()
    slot = find_slot(busy, call_minutes)
    return {
        "owner": owner,
        "date": "2026-10-19",
        "busy_intervals": [{"start": s, "end": e} for s, e in busy],
        "private_constraints_used": len(busy),
        "proposed_call": slot,
        "planner": "fixture-deterministic (NOT the dossier AI planner)",
    }
