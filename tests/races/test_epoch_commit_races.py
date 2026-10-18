"""F1: epoch-vs-commit races.

Each test forces the adversarial interleaving with explicit turn-taking
(threading.Event) — no sleeps — and shows BOTH sides:
  naive  = raw kernel use, renderer-supplied context  -> must FAIL (over-release)
  guarded = arbiter serialization boundary            -> must PASS (denied)

A race test that cannot show both is theater.
"""
import threading
import unittest
from dataclasses import replace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'packages', 'kernel'))
from kernel import Context, Fact, Kernel, Label  # noqa: E402
from arbiter import Arbiter  # noqa: E402

PRI = Label(frozenset({'priya'}), frozenset({'health'}))
SECRET = Fact('appointment', 'Prenatal visit, 15:40', PRI)


def make_clock():
    t = [100.0]
    def now():
        return t[0]
    def advance(dt):
        t[0] += dt
    return now, advance


class EpochCommitRaces(unittest.TestCase):
    # -- NAIVE path: demonstrates the race ----------------------------------
    def test_naive_audience_change_racing_commit_over_releases(self):
        """Renderer holds lease L (epoch 1). Audience changes (epoch 2).
        Renderer redeems with its STALE epoch-1 context: kernel releases.
        The invalidation never fired — nothing authoritative was consulted."""
        now, _ = make_clock()
        stale_ctx = Context('house-a', 'priya', frozenset({'priya'}), 1,
                            100.0, True, True, True, 1)
        lease = Kernel.prepare(SECRET, stale_ctx, now())
        self.assertIsNotNone(lease)

        # Meanwhile, in the real room, mom walks in (epoch -> 2). The naive
        # renderer never re-reads anything authoritative.
        result = Kernel.redeem(lease, stale_ctx, now() + 0.1)

        # FAILS OPEN relative to the room's true state: value released although
        # the audience changed. This is the race the kernel cannot express.
        self.assertEqual(result, SECRET.value)

    def test_naive_policy_bump_racing_commit_over_releases(self):
        now, _ = make_clock()
        ctx = Context('house-a', 'priya', frozenset({'priya'}), 1,
                      100.0, True, True, True, 1)
        lease = Kernel.prepare(SECRET, ctx, now())
        # Owner tightens policy (version -> 2) after prepare, before commit.
        # Naive renderer still holds the epoch-1/version-1 context.
        self.assertEqual(Kernel.redeem(lease, ctx, now() + 0.1), SECRET.value)

    # -- GUARDED path: the same interleavings, denied ------------------------
    def test_guarded_audience_change_during_commit_is_denied(self):
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)

        prepared = threading.Event()
        changed = threading.Event()
        outcome = {}

        def renderer():
            gid = arb.prepare_grant(SECRET)
            prepared.set()          # lease L bound to epoch 1
            changed.wait(5)         # ... audience changes ...
            advance(0.05)
            outcome['result'] = arb.commit(gid)

        def room():
            prepared.wait(5)
            arb.audience_changed({'priya', 'mom'})  # epoch -> 2
            changed.set()

        t1, t2 = threading.Thread(target=renderer), threading.Thread(target=room)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertIsNone(outcome['result'],
                          'commit after audience change must be denied')

    def test_guarded_policy_bump_during_commit_is_denied(self):
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid = arb.prepare_grant(SECRET)
        self.assertIsNotNone(gid)
        arb.policy_bumped()
        advance(0.05)
        self.assertIsNone(arb.commit(gid))

    def test_guarded_quiet_room_still_commits(self):
        """Control: without any race, the guarded path releases (no false deny)."""
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid = arb.prepare_grant(SECRET)
        advance(0.05)
        result = arb.commit(gid)
        self.assertIsNotNone(result)
        value, segment = result
        self.assertEqual(value, SECRET.value)
        self.assertEqual(segment.epoch, 1)
        self.assertTrue(arb.authorize_playback(segment))

    def test_commit_is_single_use_no_replay(self):
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid = arb.prepare_grant(SECRET)
        advance(0.05)
        self.assertIsNotNone(arb.commit(gid))
        advance(0.05)
        self.assertIsNone(arb.commit(gid), 'grant must not be replayable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
