"""Shared pure functions for adapters. Called explicitly — never inherited.

Everything here is stdlib-only, timezone-aware (zoneinfo), and bounded:
recurrence expands only inside an explicit window with a hard occurrence cap.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

from .contract import RecurrenceError

# Hard cap: a bounded window should never need more than this.
MAX_OCCURRENCES = 366

_SUPPORTED_FREQ = frozenset({"DAILY", "WEEKLY"})


def parse_dt(value: str, tz: str) -> datetime:
    """Parse an ISO datetime; naive values are interpreted in ``tz``."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt


def expand_recurrence(rule: Mapping, start: datetime,
                      window_start: datetime,
                      window_end: datetime) -> list:
    """Expand a recurrence rule inside [window_start, window_end).

    ``rule``: {"freq": "DAILY"|"WEEKLY", "interval": int >= 1,
               "count": int|None, "until": datetime|None,
               "byweekday": tuple[int,...]|None} (0=Monday).

    Raises RecurrenceError for unsupported frequencies or invalid rules.
    Rules with neither COUNT nor UNTIL are still bounded by the window.
    """
    freq = rule.get("freq")
    if freq not in _SUPPORTED_FREQ:
        raise RecurrenceError(
            f"unsupported recurrence freq {freq!r}; supported: "
            f"{sorted(_SUPPORTED_FREQ)}")
    interval = rule.get("interval", 1)
    if not isinstance(interval, int) or interval < 1:
        raise RecurrenceError(f"invalid interval: {interval!r}")
    count = rule.get("count")
    until = rule.get("until")
    if count is not None and (not isinstance(count, int) or count < 1):
        raise RecurrenceError(f"invalid count: {count!r}")
    if window_end <= window_start:
        raise RecurrenceError("empty expansion window")

    step = timedelta(days=interval) if freq == "DAILY" else timedelta(weeks=interval)
    byweekday = rule.get("byweekday")
    if freq == "WEEKLY" and byweekday:
        candidates = _weekly_byweekday(start, byweekday, interval)
    else:
        candidates = _arithmetic_series(start, step)

    out = []
    for i, occ in enumerate(candidates):
        if count is not None and i >= count:
            break
        if until is not None and occ > until:
            break
        if occ >= window_end:
            # Series is monotonic; weekly-byweekday is grouped per week but
            # each week's days are ascending, so a full-week overshoot ends it.
            if freq == "DAILY" or _past_week(occ, window_end, interval):
                break
            continue
        if occ >= window_start:
            out.append(occ)
        if len(out) >= MAX_OCCURRENCES:
            break
    return out


def _arithmetic_series(start: datetime, step: timedelta):
    occ = start
    while True:
        yield occ
        occ = occ + step


def _weekly_byweekday(start: datetime, byweekday: tuple, interval: int):
    week = start - timedelta(days=start.weekday())
    while True:
        for wd in sorted(byweekday):
            occ = week + timedelta(days=wd)
            occ = occ.replace(hour=start.hour, minute=start.minute,
                              second=start.second, microsecond=start.microsecond)
            if occ >= start:
                yield occ
        week = week + timedelta(weeks=interval)


def _past_week(occ: datetime, window_end: datetime, interval: int) -> bool:
    return occ >= window_end + timedelta(weeks=interval)


def derive_busy_intervals(records: Iterable,
                          window_start: datetime,
                          window_end: datetime) -> list:
    """Busy (start, end, status) intervals for records in the window.

    Skips declined/cancelled/transparent records per provider semantics —
    they occupy no busy time. Returns no titles, no attendees: this is the
    least-privilege read path (blueprint: busy intervals when they suffice).
    """
    out = []
    for rec in records:
        status = rec.derived.get("status", "confirmed")
        transparency = rec.derived.get("transparency", "opaque")
        if status in ("cancelled", "declined") or transparency == "transparent":
            continue
        start = rec.derived.get("start_dt")
        end = rec.derived.get("end_dt")
        if start is None or end is None:
            continue
        if end <= window_start or start >= window_end:
            continue
        out.append((max(start, window_start), min(end, window_end), status))
    out.sort(key=lambda t: t[0])
    return out


def all_day_range(day: date, tz: str) -> tuple:
    """An all-day event occupies [day 00:00, next day 00:00) in ``tz``."""
    zone = ZoneInfo(tz)
    start = datetime(day.year, day.month, day.day, tzinfo=zone)
    return start, start + timedelta(days=1)
