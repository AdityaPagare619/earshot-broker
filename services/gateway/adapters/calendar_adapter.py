"""Fixture calendar adapter — the first §3 adapter.

Implements the blueprint's minimum calendar handling: bounded recurrence
expansion, timezone preservation, all-day handling, declined/canceled/
transparent semantics, busy-intervals-first reads, source versions in plans,
and time-only changes that cannot touch attendees or notification flags.

Fixture-only: endpoint_allowlist is empty; no network, no OAuth flow.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from typing import FrozenSet

from earshot.kernel import Fact, Label

from . import common
from .contract import (MutationImpact, Record, RecurrenceError, SourceAdapter,
                       UnsupportedSourceError)

_OWNER = "owner"


def _L(topics=()) -> Label:
    # Private baseline: readers = {owner} only. Declassification is separate.
    return Label(frozenset({_OWNER}), frozenset(topics))


class FixtureCalendarAdapter(SourceAdapter):
    provider_id = "fixture-calendar-v1"
    endpoint_allowlist = ()
    oauth_scopes = ("calendar.readonly", "calendar.events")
    record_schema = {
        "title": "str",
        "start": "str",          # ISO datetime or ISO date (all-day)
        "end": "str",            # ISO datetime or ISO date (all-day)
        "all_day": "bool",
        "status": "str",        # confirmed | tentative | cancelled | declined
        "transparency": "str",  # opaque | transparent
        "attendees": "str",     # comma-separated ids, may be ""
        "location": "str",
        "description": "str",
        "recurrence": "str",    # "" or JSON rule dict
        "etag": "str",
    }
    subject_kinds = ("owner", "attendee")
    field_labels = {
        "title": _L(("calendar",)),
        "start": _L(("calendar",)),
        "end": _L(("calendar",)),
        "all_day": _L(("calendar",)),
        "status": _L(("calendar",)),
        "transparency": _L(("calendar",)),
        "attendees": _L(("calendar",)),
        "location": _L(("calendar",)),
        "description": _L(("calendar",)),
        "recurrence": _L(("calendar",)),
        "etag": _L(("calendar",)),
    }
    supported_transformations = ("busy_intervals", "expand_recurrence")
    mutation_recipients = {
        "reschedule": ("attendee",),   # time change notifies attendees
    }
    freshness_ttl_s = 900.0
    deletion_semantics = "tombstone"

    # -- four pure operations -------------------------------------------
    def normalize(self, raw: dict) -> Record:
        missing = set(self.record_schema) - set(raw)
        if missing:
            raise UnsupportedSourceError(
                f"malformed calendar record, missing: {sorted(missing)}")
        status = raw["status"]
        if status not in ("confirmed", "tentative", "cancelled", "declined"):
            raise UnsupportedSourceError(f"unknown status {status!r}")
        transparency = raw["transparency"]
        if transparency not in ("opaque", "transparent"):
            raise UnsupportedSourceError(
                f"unknown transparency {transparency!r}")
        tz = raw.get("timezone", "UTC")
        all_day = raw["all_day"] in (True, "true", "True", "1", 1)
        if all_day:
            start, end = common.all_day_range(
                date.fromisoformat(raw["start"]), tz)
        else:
            start = common.parse_dt(raw["start"], tz)
            end = common.parse_dt(raw["end"], tz)
        if end <= start:
            raise UnsupportedSourceError("event end <= start")
        attendees = frozenset(a.strip() for a in raw["attendees"].split(",")
                              if a.strip())
        subjects = frozenset({_OWNER}) | attendees
        return Record(
            source=self.provider_id,
            external_id=str(raw["id"]),
            version=str(raw["etag"]),
            fields={k: str(raw[k]) for k in self.record_schema},
            derived={
                "start_dt": start, "end_dt": end,
                "status": status, "transparency": transparency,
                "timezone": tz, "all_day": str(all_day),
            },
            subjects=subjects,
        )

    def label(self, record: Record) -> Label:
        lbl = self.field_labels["title"]
        for name in self.record_schema:
            if name != "title":
                lbl = lbl.join(self.field_labels[name])
        return lbl

    def plan_ops(self) -> frozenset:
        return frozenset({"load_busy_intervals", "load_event_details"})

    def mutation_impact(self, op: str) -> MutationImpact:
        if op == "reschedule":
            return MutationImpact(
                op="reschedule",
                recipients=frozenset({"attendee"}),
                side_effects=frozenset({"attendee_notification"}),
                idempotency_key_fields=("external_id", "etag"),
                # Time-only change: attendees and notification flags are
                # structurally excluded — not just conventionally avoided.
                forbidden_fields=frozenset({"attendees", "notifications"}),
            )
        raise UnsupportedSourceError(f"unknown mutation op {op!r}")

    # -- adapter-specific typed reads ------------------------------------
    def busy_intervals(self, records, window_start: datetime,
                       window_end: datetime) -> list:
        """Least-privilege read path: (start, end, status) only.

        No titles, no attendees, no descriptions cross this boundary.
        """
        return common.derive_busy_intervals(records, window_start,
                                            window_end)

    def expand(self, record: Record, window_start: datetime,
               window_end: datetime) -> list:
        """Occurrences of a (possibly recurring) record in the window.

        Returns [(start, end, flags)] where flags may contain
        "recurrence_unsupported" for the single master occurrence fallback.
        Never silently dropped, never infinitely expanded.
        """
        raw_rule = record.fields.get("recurrence", "")
        start, end = record.derived["start_dt"], record.derived["end_dt"]
        if not raw_rule:
            if end <= window_start or start >= window_end:
                return []
            return [(start, end, frozenset())]
        rule = json.loads(raw_rule)
        try:
            occs = common.expand_recurrence(rule, start, window_start,
                                             window_end)
        except RecurrenceError:
            return [(start, end, frozenset({"recurrence_unsupported"}))]
        duration = end - start
        return [(o, o + duration, frozenset()) for o in occs]
