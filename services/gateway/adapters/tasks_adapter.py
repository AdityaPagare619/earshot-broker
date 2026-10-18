"""Fixture tasks/reminders adapter — the SECOND §3 adapter.

This is the generalization proof: a different domain (no attendees, no
locations, no busy intervals; due dates instead of intervals; poll-based
freshness instead of webhooks; list-scoped mutations with no external
recipients) running through the same kernel, the same contract, the same
tools. Zero imports from ``calendar_adapter`` — shared logic comes only
from ``common.py`` pure functions.

Field-label note: a task in the "medication" list carries the "health"
topic in addition to "tasks". This is bounded, declared topic inference —
not AI classification. The mapping lives in ``LIST_TOPICS`` below, reviewed
as code.
"""
from __future__ import annotations

import json
from datetime import date as _date
from datetime import datetime
from typing import FrozenSet
from zoneinfo import ZoneInfo

from kernel import Fact, Label

from . import common
from .contract import (MutationImpact, Record, RecurrenceError, SourceAdapter,
                       UnsupportedSourceError)

_OWNER = "owner"

# Declared list -> topic mapping. Bounded and reviewable; not a classifier.
LIST_TOPICS = {
    "medication": ("tasks", "health"),
    "groceries": ("tasks",),
    "chores": ("tasks",),
    "work": ("tasks", "work"),
}


def _L(list_id: str) -> Label:
    return Label(frozenset({_OWNER}), frozenset(LIST_TOPICS.get(list_id, ("tasks",))))


class FixtureTasksAdapter(SourceAdapter):
    provider_id = "fixture-tasks-v1"
    endpoint_allowlist = ()
    oauth_scopes = ("tasks.readonly",)
    record_schema = {
        "title": "str",
        "due": "str",            # ISO datetime, ISO date, or "" (no due date)
        "notes": "str",
        "status": "str",        # needsAction | completed
        "list_id": "str",       # task list, e.g. "medication"
        "repeat": "str",        # "" or JSON rule dict (DAILY/WEEKLY only)
        "etag": "str",
    }
    subject_kinds = ("owner",)
    # Labels are list-dependent; the class-level baseline uses the default
    # ("tasks",) topic and label() refines per record. Every schema field is
    # covered here, satisfying contract_check.
    field_labels = {
        "title": Label(frozenset({_OWNER}), frozenset(("tasks",))),
        "due": Label(frozenset({_OWNER}), frozenset(("tasks",))),
        "notes": Label(frozenset({_OWNER}), frozenset(("tasks",))),
        "status": Label(frozenset({_OWNER}), frozenset(("tasks",))),
        "list_id": Label(frozenset({_OWNER}), frozenset(("tasks",))),
        "repeat": Label(frozenset({_OWNER}), frozenset(("tasks",))),
        "etag": Label(frozenset({_OWNER}), frozenset(("tasks",))),
    }
    supported_transformations = ("due_within", "expand_repeat")
    mutation_recipients = {
        "complete_task": (),     # list-scoped: no external human is notified
        "reschedule_task": (),  # same: moving your own reminder notifies nobody
    }
    freshness_ttl_s = 3600.0    # poll-based; no webhook equivalent declared
    deletion_semantics = "purge"

    # -- four pure operations -------------------------------------------
    def normalize(self, raw: dict) -> Record:
        missing = set(self.record_schema) - set(raw)
        if missing:
            raise UnsupportedSourceError(
                f"malformed task record, missing: {sorted(missing)}")
        status = raw["status"]
        if status not in ("needsAction", "completed"):
            raise UnsupportedSourceError(f"unknown status {status!r}")
        tz = raw.get("timezone", "UTC")
        due_raw = raw["due"]
        if due_raw:
            try:
                due = common.parse_dt(due_raw, tz)
            except ValueError:
                # ISO date (no time): due at start of day in tz.
                d = _date.fromisoformat(due_raw)
                due = datetime(d.year, d.month, d.day, tzinfo=ZoneInfo(tz))
        else:
            due = None
        return Record(
            source=self.provider_id,
            external_id=str(raw["id"]),
            version=str(raw["etag"]),
            fields={k: str(raw[k]) for k in self.record_schema},
            derived={"due_dt": due, "status": status, "timezone": tz,
                      "list_id": str(raw["list_id"])},
            subjects=frozenset({_OWNER}),
        )

    def label(self, record: Record) -> Label:
        list_id = record.derived.get("list_id", "")
        lbl = _L(list_id)
        # Join is idempotent here (same readers) but keeps the invariant:
        # label = join of per-field labels, refined by list topics.
        for name in self.record_schema:
            lbl = lbl.join(self.field_labels[name])
        return lbl

    def plan_ops(self) -> frozenset:
        return frozenset({"load_flexible_tasks", "load_task_details"})

    def mutation_impact(self, op: str) -> MutationImpact:
        if op in ("complete_task", "reschedule_task"):
            return MutationImpact(
                op=op,
                recipients=frozenset(),   # nobody outside EARSHOT observes
                side_effects=frozenset(),
                idempotency_key_fields=("external_id", "etag"),
            )
        raise UnsupportedSourceError(f"unknown mutation op {op!r}")

    # -- adapter-specific typed reads ------------------------------------
    def due_within(self, records, window_start: datetime,
                   window_end: datetime) -> list:
        """Records due in [window_start, window_end), needsAction only.

        The task-domain analogue of busy intervals: minimal fields for
        scheduling (id + due), never notes/titles in the minimal path.
        Completed tasks are excluded — they constrain nothing.
        """
        out = []
        for rec in records:
            if rec.derived.get("status") != "needsAction":
                continue
            due = rec.derived.get("due_dt")
            if due is None:
                continue
            if window_start <= due < window_end:
                out.append((rec.external_id, due))
        out.sort(key=lambda t: t[1])
        return out

    def expand_repeat(self, record: Record, window_start: datetime,
                      window_end: datetime) -> list:
        """Repeated tasks materialize as occurrences in the window.

        Returns [(due, flags)]. Unsupported repeat -> single occurrence with
        the "repeat_unsupported" flag; never silently dropped.
        """
        raw_rule = record.fields.get("repeat", "")
        due = record.derived.get("due_dt")
        if due is None:
            return []
        if not raw_rule:
            if window_start <= due < window_end:
                return [(due, frozenset())]
            return []
        rule = json.loads(raw_rule)
        try:
            occs = common.expand_recurrence(rule, due, window_start,
                                             window_end)
        except RecurrenceError:
            if window_start <= due < window_end:
                return [(due, frozenset({"repeat_unsupported"}))]
            return []
        return [(o, frozenset()) for o in occs]
