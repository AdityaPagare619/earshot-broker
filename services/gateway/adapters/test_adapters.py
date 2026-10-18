"""Adapter tests v1: contract enforcement, registry fail-private, calendar.

Run: python3 test_adapters.py  (stdlib unittest; run from this directory)
"""
import json
import sys
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# kernel package + this package's parent (services/gateway) for `adapters` imports.
sys.path.insert(0, str(_HERE.parent.parent.parent / "packages" / "kernel"))
sys.path.insert(0, str(_HERE.parent))

from kernel import Fact, Label  # noqa: E402
from adapters.contract import (AdapterRegistry, ContractViolation,  # noqa: E402
                               RecurrenceError, SourceAdapter,
                               UnsupportedSourceError, contract_check)
from adapters.calendar_adapter import FixtureCalendarAdapter  # noqa: E402
from adapters import common  # noqa: E402

UTC = ZoneInfo("UTC")
AD = FixtureCalendarAdapter()


def ev(**kw):
    base = {"id": "e1", "title": "Dentist", "start": "2026-10-20T10:00:00",
            "end": "2026-10-20T10:30:00", "all_day": False,
            "status": "confirmed", "transparency": "opaque", "attendees": "",
            "location": "", "description": "", "recurrence": "",
            "etag": "v1", "timezone": "UTC"}
    base.update(kw)
    return base


class ContractTests(unittest.TestCase):
    def test_calendar_passes_contract_check(self):
        contract_check(AD)  # raises nothing

    def test_missing_label_fails_contract(self):
        class Broken(FixtureCalendarAdapter):
            provider_id = "broken-v1"
            field_labels = {}  # nothing labeled
        with self.assertRaises(ContractViolation):
            contract_check(Broken())

    def test_registry_unknown_source_fails_private(self):
        reg = AdapterRegistry()
        reg.register(AD)
        with self.assertRaises(UnsupportedSourceError) as cm:
            reg.get("evil-source")
        self.assertIn("failing private", str(cm.exception))

    def test_registry_duplicate_rejected(self):
        reg = AdapterRegistry()
        reg.register(AD)
        with self.assertRaises(ContractViolation):
            reg.register(FixtureCalendarAdapter())

    def test_every_emitted_fact_is_private_baseline(self):
        rec = AD.normalize(ev(attendees="ravi"))
        for fact in AD.facts(rec):
            self.assertTrue(fact.label.readers <= frozenset({"owner"}),
                            f"fact {fact.key} leaks readers {fact.label.readers}")

    def test_label_join_keeps_private(self):
        rec = AD.normalize(ev())
        lbl = AD.label(rec)
        self.assertNotIn("*", lbl.readers)


class CalendarNormalizeTests(unittest.TestCase):
    def test_normalize_ok(self):
        rec = AD.normalize(ev(attendees="ravi, mom"))
        self.assertEqual(rec.subjects, frozenset({"owner", "ravi", "mom"}))
        self.assertEqual(rec.version, "v1")

    def test_all_day_becomes_date_range(self):
        rec = AD.normalize(ev(all_day=True, start="2026-10-20",
                               end="2026-10-21"))
        s, e = rec.derived["start_dt"], rec.derived["end_dt"]
        self.assertEqual((s.hour, e.hour), (0, 0))
        self.assertEqual((e - s), timedelta(days=1))

    def test_bad_status_rejected(self):
        with self.assertRaises(UnsupportedSourceError):
            AD.normalize(ev(status="maybe"))

    def test_end_before_start_rejected(self):
        with self.assertRaises(UnsupportedSourceError):
            AD.normalize(ev(start="2026-10-20T11:00:00",
                             end="2026-10-20T10:00:00"))

    def test_naive_datetime_gets_timezone(self):
        rec = AD.normalize(ev(timezone="Asia/Kolkata"))
        self.assertEqual(str(rec.derived["start_dt"].tzinfo),
                         "Asia/Kolkata")


class BusyIntervalTests(unittest.TestCase):
    def _recs(self):
        raws = [
            ev(id="a", start="2026-10-20T10:00:00", end="2026-10-20T11:00:00"),
            ev(id="b", start="2026-10-20T12:00:00", end="2026-10-20T13:00:00",
               status="declined"),
            ev(id="c", start="2026-10-20T14:00:00", end="2026-10-20T15:00:00",
               status="cancelled"),
            ev(id="d", start="2026-10-20T16:00:00", end="2026-10-20T17:00:00",
               transparency="transparent"),
            ev(id="e", title="Secret project sync",
               start="2026-10-20T18:00:00", end="2026-10-20T19:00:00"),
        ]
        return [AD.normalize(r) for r in raws]

    def test_busy_intervals_skip_non_blocking(self):
        recs = self._recs()
        ivs = AD.busy_intervals(
            recs, datetime(2026, 10, 20, tzinfo=UTC),
            datetime(2026, 10, 21, tzinfo=UTC))
        self.assertEqual(len(ivs), 2)  # only a and e

    def test_busy_intervals_carry_no_titles(self):
        recs = self._recs()
        ivs = AD.busy_intervals(
            recs, datetime(2026, 10, 20, tzinfo=UTC),
            datetime(2026, 10, 21, tzinfo=UTC))
        blob = json.dumps(ivs, default=str)
        self.assertNotIn("Secret project sync", blob)
        self.assertNotIn("Dentist", blob)


class RecurrenceTests(unittest.TestCase):
    def _expand(self, rule, start="2026-10-20T10:00:00"):
        rec = AD.normalize(ev(id="r", recurrence=json.dumps(rule),
                               start=start, end="2026-10-20T10:30:00"))
        return AD.expand(rec, datetime(2026, 10, 20, tzinfo=UTC),
                         datetime(2026, 10, 30, tzinfo=UTC))

    def test_daily_count(self):
        occs = self._expand({"freq": "DAILY", "interval": 1, "count": 3})
        self.assertEqual(len(occs), 3)
        self.assertTrue(all(f == frozenset() for _, _, f in occs))

    def test_weekly_byweekday(self):
        # COUNT is global per RRULE (counts all occurrences, not in-window
        # ones): occurrences are Oct 21, 26, 28, Nov 2 -> 3 land in-window.
        occs = self._expand({"freq": "WEEKLY", "interval": 1,
                              "byweekday": (0, 2),  # Mon/Wed
                              "count": 4})
        self.assertEqual(len(occs), 3)
        self.assertEqual([o.weekday() for o, _, _ in occs], [2, 0, 2])

    def test_window_bounds(self):
        occs = self._expand({"freq": "DAILY", "interval": 1})  # unbounded rule
        for o, _, _ in occs:
            self.assertLess(o, datetime(2026, 10, 30, tzinfo=UTC))

    def test_monthly_unsupported_flagged_not_dropped(self):
        occs = self._expand({"freq": "MONTHLY", "interval": 1, "count": 3})
        self.assertEqual(len(occs), 1)
        self.assertIn("recurrence_unsupported", occs[0][2])

    def test_common_raises_directly(self):
        with self.assertRaises(RecurrenceError):
            common.expand_recurrence(
                {"freq": "YEARLY"}, datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2027, 1, 1, tzinfo=UTC))


class MutationTests(unittest.TestCase):
    def test_reschedule_impact(self):
        mi = AD.mutation_impact("reschedule")
        self.assertEqual(mi.recipients, frozenset({"attendee"}))
        self.assertIn("attendees", mi.forbidden_fields)
        self.assertIn("notifications", mi.forbidden_fields)

    def test_unknown_mutation_op(self):
        with self.assertRaises(UnsupportedSourceError):
            AD.mutation_impact("delete_everything")

    def test_idempotency_key_stable(self):
        rec = AD.normalize(ev())
        k1 = AD.idempotency_key("reschedule", rec)
        rec2 = AD.normalize(ev(title="Changed title"))
        k2 = AD.idempotency_key("reschedule", rec2)
        self.assertEqual(k1, k2)  # title not in key fields
        rec3 = AD.normalize(ev(etag="v2"))
        self.assertNotEqual(k1, AD.idempotency_key("reschedule", rec3))



# ---------------------------------------------------------------- v2: tasks
from adapters.tasks_adapter import FixtureTasksAdapter  # noqa: E402

TA = FixtureTasksAdapter()


def task(**kw):
    base = {"id": "t1", "title": "Take vitamins", "due": "2026-10-20T08:00:00",
            "notes": "with breakfast", "status": "needsAction",
            "list_id": "medication", "repeat": "", "etag": "v1",
            "timezone": "UTC"}
    base.update(kw)
    return base


class TasksContractTests(unittest.TestCase):
    def test_tasks_passes_contract_check(self):
        contract_check(TA)

    def test_plan_ops_disjoint_from_calendar(self):
        self.assertTrue(TA.plan_ops().isdisjoint(AD.plan_ops()))

    def test_no_import_of_calendar_adapter(self):
        import adapters.tasks_adapter as mod
        with open(mod.__file__) as fh:
            import_lines = [l for l in fh.read().splitlines()
                            if l.strip().startswith(("import ", "from "))]
        self.assertFalse(any("calendar_adapter" in l for l in import_lines),
                         "tasks adapter must not import the calendar adapter")

    def test_medication_topic_declared(self):
        rec = TA.normalize(task())
        lbl = TA.label(rec)
        self.assertIn("health", lbl.topics)
        self.assertIn("tasks", lbl.topics)
        self.assertEqual(lbl.readers, frozenset({"owner"}))

    def test_grocery_task_no_health_topic(self):
        rec = TA.normalize(task(list_id="groceries", id="t2"))
        self.assertNotIn("health", TA.label(rec).topics)

    def test_mutations_have_no_external_recipients(self):
        for op in ("complete_task", "reschedule_task"):
            mi = TA.mutation_impact(op)
            self.assertEqual(mi.recipients, frozenset())
            self.assertEqual(mi.side_effects, frozenset())

    def test_due_within_minimal_fields(self):
        recs = [TA.normalize(task()),
                TA.normalize(task(id="t2", due="2026-10-21T08:00:00")),
                TA.normalize(task(id="t3", status="completed")),
                TA.normalize(task(id="t4", due=""))]
        out = TA.due_within(recs, datetime(2026, 10, 20, tzinfo=UTC),
                            datetime(2026, 10, 21, tzinfo=UTC))
        self.assertEqual([i for i, _ in out], ["t1"])
        blob = json.dumps(out, default=str)
        self.assertNotIn("vitamins", blob)
        self.assertNotIn("breakfast", blob)

    def test_repeat_expansion(self):
        rec = TA.normalize(task(id="t5", repeat=json.dumps(
            {"freq": "DAILY", "interval": 1, "count": 3})))
        occs = TA.expand_repeat(rec,
                                datetime(2026, 10, 20, tzinfo=UTC),
                                datetime(2026, 10, 30, tzinfo=UTC))
        self.assertEqual(len(occs), 3)

    def test_unsupported_repeat_flagged(self):
        rec = TA.normalize(task(id="t6", repeat=json.dumps(
            {"freq": "MONTHLY", "interval": 1})))
        occs = TA.expand_repeat(rec,
                                datetime(2026, 10, 20, tzinfo=UTC),
                                datetime(2026, 10, 30, tzinfo=UTC))
        self.assertEqual(len(occs), 1)
        self.assertIn("repeat_unsupported", occs[0][1])

    def test_facts_private_baseline(self):
        rec = TA.normalize(task())
        for fact in TA.facts(rec):
            self.assertEqual(fact.label.readers, frozenset({"owner"}))


class ThirdAdapterTests(unittest.TestCase):
    """The falsifiability test from the verdict: a third source shape must
    register against the frozen contract with zero base-code changes."""

    def test_notes_adapter_registers(self):
        from adapters.contract import SourceAdapter, MutationImpact, Record

        class NotesAdapter(SourceAdapter):
            provider_id = "fixture-notes-v1"
            endpoint_allowlist = ()
            oauth_scopes = ("notes.readonly",)
            record_schema = {"title": "str", "body": "str", "etag": "str"}
            subject_kinds = ("owner",)
            field_labels = {
                "title": Label(frozenset({"owner"}), frozenset({"notes"})),
                "body": Label(frozenset({"owner"}), frozenset({"notes"})),
                "etag": Label(frozenset({"owner"}), frozenset({"notes"})),
            }
            supported_transformations = ()
            mutation_recipients = {}
            freshness_ttl_s = 3600.0
            deletion_semantics = "purge"

            def normalize(self, raw):
                return Record(source=self.provider_id,
                              external_id=str(raw["id"]),
                              version=str(raw["etag"]),
                              fields={k: str(raw[k]) for k in self.record_schema})

            def label(self, record):
                lbl = self.field_labels["title"]
                for n in ("body", "etag"):
                    lbl = lbl.join(self.field_labels[n])
                return lbl

            def plan_ops(self):
                return frozenset({"load_notes"})

            def mutation_impact(self, op):
                raise UnsupportedSourceError(op)

        reg = AdapterRegistry()
        reg.register(NotesAdapter())  # no base-code change needed
        self.assertIn("fixture-notes-v1", reg.provider_ids())


class KernelIntegrationTests(unittest.TestCase):
    """Adapters plug into the real kernel: labels gate projections."""

    def test_private_task_fact_withheld_from_public_host(self):
        from kernel import Kernel
        from dataclasses import replace
        k = Kernel()
        rec = TA.normalize(task())  # medication/health, owner-only readers
        facts = TA.facts(rec)
        ctx = __import__("kernel", fromlist=["Context"]).Context(
            "house-a", "owner", frozenset({"owner"}), 1, 100.0,
            True, True, False, 1)  # uncontrolled host
        proj = k.room_projection(facts, ctx, 100.0)
        self.assertEqual(proj, ())  # nothing crosses to an uncontrolled host



# ------------------------------------------------------- v3: hardening
from adapters.plan_ops import (AmbiguousPlanOp, UnknownPlanOp,  # noqa: E402
                               known_ops, validate_plan_ops)
from adapters import default_registry  # noqa: E402


class RegistrySyncTests(unittest.TestCase):
    def test_freshness_lifecycle(self):
        reg = AdapterRegistry()
        reg.register(AD)
        self.assertFalse(reg.is_fresh("fixture-calendar-v1", now=1000.0))
        recs = [AD.normalize(ev())]
        reg.mark_synced("fixture-calendar-v1", recs, now=1000.0)
        self.assertTrue(reg.is_fresh("fixture-calendar-v1", now=1000.0 + 100))
        self.assertFalse(reg.is_fresh("fixture-calendar-v1",
                                      now=1000.0 + AD.freshness_ttl_s + 1))

    def test_stale_version_fails_closed(self):
        from adapters.contract import AdapterError
        reg = AdapterRegistry()
        reg.register(AD)
        reg.mark_synced("fixture-calendar-v1", [AD.normalize(ev())], now=0.0)
        stale = AD.normalize(ev(etag="v0"))
        with self.assertRaises(AdapterError):
            reg.check_version(stale)

    def test_tombstone_deletion(self):
        from adapters.contract import AdapterError
        reg = AdapterRegistry()
        reg.register(AD)  # calendar declares tombstone
        reg.mark_synced("fixture-calendar-v1", [AD.normalize(ev())], now=0.0)
        self.assertEqual(reg.note_deletion("fixture-calendar-v1", "e1"),
                         "tombstoned")
        self.assertTrue(reg.is_deleted("fixture-calendar-v1", "e1"))
        with self.assertRaises(AdapterError):
            reg.check_version(AD.normalize(ev()))

    def test_purge_deletion(self):
        reg = AdapterRegistry()
        reg.register(TA)  # tasks declares purge
        recs = [TA.normalize(task())]
        reg.mark_synced("fixture-tasks-v1", recs, now=0.0)
        self.assertEqual(reg.note_deletion("fixture-tasks-v1", "t1"), "purged")
        self.assertFalse(reg.is_deleted("fixture-tasks-v1", "t1"))


class PlanOpTests(unittest.TestCase):
    def test_validate_known_ops(self):
        reg = default_registry()
        owners = validate_plan_ops(reg, ["load_busy_intervals",
                                         "load_flexible_tasks"])
        self.assertEqual(owners["load_busy_intervals"], "fixture-calendar-v1")
        self.assertEqual(owners["load_flexible_tasks"], "fixture-tasks-v1")

    def test_unknown_op_rejected(self):
        reg = default_registry()
        with self.assertRaises(UnknownPlanOp):
            validate_plan_ops(reg, ["drop_tables"])

    def test_ambiguous_op_rejected(self):
        from adapters.contract import SourceAdapter, MutationImpact, Record
        from adapters.calendar_adapter import FixtureCalendarAdapter

        class Copycat(FixtureCalendarAdapter):
            provider_id = "copycat-v1"

        reg = default_registry()
        reg.register(Copycat())
        with self.assertRaises(AmbiguousPlanOp):
            validate_plan_ops(reg, ["load_busy_intervals"])

    def test_known_ops_union(self):
        reg = default_registry()
        self.assertIn("load_busy_intervals", known_ops(reg))
        self.assertIn("load_flexible_tasks", known_ops(reg))


class DSTEdgeTests(unittest.TestCase):
    def test_all_day_across_dst_transition(self):
        # America/New_York falls back on 2026-11-01; an all-day event must
        # still be exactly one calendar day, not 25 hours of confusion.
        rec = AD.normalize(ev(all_day=True, start="2026-11-01",
                               end="2026-11-02", timezone="America/New_York"))
        s, e = rec.derived["start_dt"], rec.derived["end_dt"]
        self.assertEqual((s.utcoffset().total_seconds(),
                          e.utcoffset().total_seconds()), (-14400.0, -18000.0))
        self.assertEqual(s.date().isoformat(), "2026-11-01")

    def test_recurrence_across_dst_keeps_wall_time(self):
        import json as _json
        rec = AD.normalize(ev(id="r2", timezone="America/New_York",
                               start="2026-10-30T09:00:00",
                               end="2026-10-30T09:30:00",
                               recurrence=_json.dumps({"freq": "DAILY",
                                                       "interval": 1,
                                                       "count": 5})))
        occs = AD.expand(rec, datetime(2026, 10, 30, tzinfo=ZoneInfo("UTC")),
                         datetime(2026, 11, 6, tzinfo=ZoneInfo("UTC")))
        # wall-clock 09:00 preserved across the Nov 1 fallback
        self.assertTrue(all(o.hour == 9 and o.minute == 0 for o, _, _ in occs))


if __name__ == "__main__":
    unittest.main(verbosity=1)
