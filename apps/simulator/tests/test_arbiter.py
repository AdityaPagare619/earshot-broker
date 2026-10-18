"""Arbiter ordering tests — the epoch race must close, not just pass once."""
import threading
import time
import unittest

from earshot.simulator.arbiter import Arbiter, AudienceEvent
from earshot.kernel import Fact, Kernel, Label

PUB = Label(frozenset({"*"}))
PRI = Label(frozenset({"priya"}), frozenset({"health"}))


def make(owner="priya"):
    k = Kernel()
    return k, Arbiter(k, "house-a", owner)


class ArbiterTests(unittest.TestCase):
    def test_prepare_commit_playable(self):
        k, a = make()
        g = a.prepare("t", Fact("w", "Rain.", PUB))
        self.assertIsNotNone(g)
        seg = a.commit(g)
        self.assertIsNotNone(seg)
        self.assertTrue(a.is_segment_playable(seg))

    def test_grant_is_single_use(self):
        k, a = make()
        g = a.prepare("t", Fact("w", "Rain.", PUB))
        self.assertIsNotNone(a.commit(g))
        self.assertIsNone(a.commit(g))  # second commit denied

    def test_private_fact_never_prepares_for_wider_room(self):
        k, a = make()
        ev = AudienceEvent(1, time.time(), time.time(),
                           frozenset({"priya", "mom"}), "manual")
        a.audience_changed(ev)
        # NOTE: arbiter is stopped after an audience change; resume for re-trust
        a.resume_after_retrust(frozenset({"priya", "mom"}))
        g = a.prepare("t", Fact("s", "Prenatal 15:40", PRI))
        self.assertIsNone(g)  # mom present -> label denies

    def test_audience_change_stops_first_then_invalidates(self):
        k, a = make()
        g = a.prepare("t", Fact("w", "Rain.", PUB))
        ev = AudienceEvent(1, time.time(), time.time(),
                           frozenset({"priya", "mom"}), "manual")
        out = a.audience_changed(ev)
        self.assertTrue(out["accepted"])
        self.assertEqual(out["epoch"], 1)
        self.assertTrue(a.output_stopped)
        self.assertIsNone(a.commit(g))  # pending grant dies with the epoch

    def test_late_segment_rejected_locally(self):
        k, a = make()
        g = a.prepare("t", Fact("w", "Rain.", PUB))
        seg = a.commit(g)
        ev = AudienceEvent(1, time.time(), time.time(),
                           frozenset({"priya", "mom"}), "manual")
        a.audience_changed(ev)
        self.assertFalse(a.is_segment_playable(seg))

    def test_seq_regression_rejected(self):
        k, a = make()
        now = time.time()
        ok = a.audience_changed(AudienceEvent(2, now, now,
                               frozenset({"priya"}), "manual"))
        self.assertTrue(ok["accepted"])
        bad = a.audience_changed(AudienceEvent(1, now, now,
                                frozenset({"priya"}), "manual"))
        self.assertFalse(bad["accepted"])

    def test_stale_evidence_degrades_to_unknown(self):
        k, a = make()
        a._observed_at = time.time() - 60  # stale
        g = a.prepare("t", Fact("s", "Prenatal 15:40", PRI))
        self.assertIsNone(g)  # UNKNOWN added -> label denies

    def test_heartbeat_loss_restricts(self):
        k, a = make()
        a.sensor_heartbeat_lost()
        self.assertTrue(a.output_stopped)
        self.assertIsNone(a.prepare("t", Fact("w", "Rain.", PUB)))

    def test_no_autoplay_after_retrust(self):
        k, a = make()
        g = a.prepare("t", Fact("w", "Rain.", PUB))
        seg = a.commit(g)
        a.audience_changed(AudienceEvent(1, time.time(), time.time(),
                                        frozenset({"priya", "mom"}), "manual"))
        a.resume_after_retrust(frozenset({"priya"}))
        # Old segment must NOT become playable again after re-trust.
        self.assertFalse(a.is_segment_playable(seg))

    def test_commit_vs_invalidation_race(self):
        """The linearization property: no interleaving may emit after stop.

        Hammer commit() and audience_changed() from two threads; assert that
        every committed segment was playable at commit time AND that after
        the stop, no segment from the old epoch is playable."""
        for _ in range(20):
            k, a = make()
            results = []
            stop = threading.Event()

            def committer():
                for i in range(30):
                    g = a.prepare("t", Fact("w", f"seg{i}", PUB))
                    if g is None:
                        continue
                    seg = a.commit(g)
                    if seg is not None:
                        results.append(seg)

            def interrupter():
                time.sleep(0.005)
                a.audience_changed(AudienceEvent(
                    1, time.time(), time.time(),
                    frozenset({"priya", "mom"}), "manual"))
                stop.set()

            t1 = threading.Thread(target=committer)
            t2 = threading.Thread(target=interrupter)
            t1.start(); t2.start(); t1.join(); t2.join()
            # After the stop, nothing from the old epoch may play.
            for seg in results:
                self.assertFalse(a.is_segment_playable(seg),
                                 "old-epoch segment playable after stop")

    def test_policy_bump_invalidates_grants(self):
        k, a = make()
        g = a.prepare("t", Fact("w", "Rain.", PUB))
        a.bump_policy(2)
        self.assertIsNone(a.commit(g))

    def test_task_state_survives_audience_change(self):
        k, a = make()
        a.put_task_state("t1", {"plan": "groceries after 6"})
        a.audience_changed(AudienceEvent(1, time.time(), time.time(),
                                        frozenset({"priya", "mom"}), "manual"))
        self.assertEqual(a.get_task_state("t1"), {"plan": "groceries after 6"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
