"""Adapter tests v1: contract enforcement, registry fail-private, calendar.

Run: python3 test_adapters.py  (stdlib unittest; run from this directory)
"""
import json
import sys
import os
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
# kernel package + this package's parent (services/gateway) for `adapters` imports.
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "packages", "kernel"))
sys.path.insert(0, os.path.join(_HERE, ".."))

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


if __name__ == "__main__":
    unittest.main(verbosity=1)
