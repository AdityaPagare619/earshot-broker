"""F6/F7: stale-sensor and trust-boundary races.

F6: Label.allows(frozenset()) is True for ANY label — with valid evidence of
    an empty room, secrets cross into the renderer. Pinned as intended-but-
    load-bearing: "nobody present" is exactly what a lying sensor claims.
F7: observed_at is caller-supplied. The kernel's TTL check measures the age of
    the *timestamp*, not the liveness of the *sensor*. A forged-fresh timestamp
    is indistinguishable from a true-fresh one — the kernel cannot tell, so the
    test asserts the indistinguishability and documents the trust boundary.
"""
import unittest
from dataclasses import replace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'packages', 'kernel'))
from kernel import Context, Fact, Kernel, Label  # noqa: E402
from arbiter import Arbiter  # noqa: E402

PRI = Label(frozenset({'priya'}), frozenset({'health'}))
SECRET = Fact('appointment', 'Prenatal visit, 15:40', PRI)
PUB = Label(frozenset({'*'}))
PUBLIC_FACT = Fact('weather', 'Rain is forecast.', PUB)


def make_clock():
    t = [100.0]
    def now():
        return t[0]
    def advance(dt):
        t[0] += dt
    return now, advance


class SensorRaces(unittest.TestCase):
    def test_empty_audience_releases_everything(self):
        """F6 pinned: empty audience + valid evidence -> secret crosses.
        Intended ('nobody listening') but load-bearing: the claim 'nobody is
        present' comes from whoever minted the Context."""
        ctx = Context('house-a', 'priya', frozenset(), 1, 100.0,
                      True, True, True, 1)
        out = Kernel.room_projection((PUBLIC_FACT, SECRET), ctx, 100.0)
        self.assertIn(SECRET.value, out,
                      'empty audience allows any label: pinned behavior')

    def test_forged_fresh_timestamp_indistinguishable(self):
        """F7: sensor died at t=90 but renderer forges observed_at=99.9.
        Kernel behavior is IDENTICAL to a truly-fresh sensor — the trust
        boundary is at Context minting, not inside the kernel."""
        honest = Context('house-a', 'priya', frozenset({'priya'}), 1, 99.9,
                         True, True, True, 1)   # sensor truly saw at 99.9
        forged = Context('house-a', 'priya', frozenset({'priya'}), 1, 99.9,
                         True, True, True, 1)   # sensor dead since 90; lied
        self.assertEqual(
            Kernel.room_projection((SECRET,), honest, 100.0),
            Kernel.room_projection((SECRET,), forged, 100.0),
            'kernel cannot distinguish forged freshness: trust boundary noted')

    def test_sensor_death_between_prepare_and_redeem_denies(self):
        """Good behavior: evidence_valid flips False mid-flight -> redeem
        denies (UNKNOWN poisons the audience). The heartbeat path works when
        the signal is honest."""
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid = arb.prepare_grant(SECRET)
        self.assertIsNotNone(gid)
        arb.sensor_died()  # heartbeat stops: §11.2 expire-the-lease path
        advance(0.05)
        self.assertIsNone(arb.commit(gid),
                          'dead sensor must deny the pending grant')

    def test_sensor_recovery_restores_release(self):
        """Control: after honest recovery, the guarded path releases again."""
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        arb.sensor_died()
        arb.sensor_recovered({'priya'})
        gid = arb.prepare_grant(SECRET)
        self.assertIsNotNone(gid)
        advance(0.05)
        self.assertIsNotNone(arb.commit(gid))

    def test_unknown_in_label_readers_is_a_footgun(self):
        """Adversarial policy authoring: readers={'priya','UNKNOWN'} lets a
        stale-evidence audience (priya + UNKNOWN) read the 'private' fact.
        The kernel is correct per the label; the label is the vulnerability."""
        footgun = Label(frozenset({'priya', 'UNKNOWN'}), frozenset({'health'}))
        bait = Fact('note', 'Bait note', footgun)
        stale = Context('house-a', 'priya', frozenset({'priya'}), 1, 100.0,
                        False, True, True, 1)  # evidence dead -> +UNKNOWN
        out = Kernel.room_projection((bait,), stale, 100.0)
        self.assertIn('Bait note', out,
                      'UNKNOWN in readers defeats stale-evidence protection')

    def test_heartbeat_gap_vs_timestamp_age(self):
        """F7 mechanism, pinned: two contexts with the same observed_at but
        different true sensor liveness produce the same effective audience.
        The TTL measures timestamp age, never sensor liveness."""
        now, _ = make_clock()
        live = Context('house-a', 'priya', frozenset({'priya'}), 1, 99.5,
                       True, True, True, 1)
        dead = replace(live)  # same timestamp; sensor actually dead — kernel blind
        self.assertEqual(live.effective_audience(now(), ttl=1.0),
                         dead.effective_audience(now(), ttl=1.0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
