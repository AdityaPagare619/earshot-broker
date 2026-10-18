"""F4/F5: lease invalidation races.

F4: leases carry no sequence number and no candidate digest; a value redeemed
    legitimately can be buffered and played after the epoch advanced. The kernel
    denied the *redeem*; nothing stops the *playback*.
F5: capsules have revoke(); leases don't. Withdrawing one pending grant while
    another is mid-flight has no surgical primitive — only the epoch sledgehammer.
"""
import threading
import unittest

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


class LeaseRaces(unittest.TestCase):
    def test_bearer_lease_redeems_twice_naive(self):
        """F4 (naive): the same lease object redeems repeatedly — bearer
        semantics with no server-side record. Documents the replay property."""
        now, advance = make_clock()
        ctx = Context('house-a', 'priya', frozenset({'priya'}), 1,
                      100.0, True, True, True, 1)
        lease = Kernel.prepare(SECRET, ctx, now())
        advance(0.05)
        self.assertEqual(Kernel.redeem(lease, ctx, now()), SECRET.value)
        advance(0.05)
        # Second redeem of the identical lease still succeeds: no consumption.
        self.assertEqual(Kernel.redeem(lease, ctx, now()), SECRET.value)

    def test_guarded_commit_is_single_use(self):
        """F4 (guarded): the arbiter deletes the grant on commit — replay denied."""
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid = arb.prepare_grant(SECRET)
        advance(0.05)
        first = arb.commit(gid)
        self.assertIsNotNone(first)
        advance(0.05)
        self.assertIsNone(arb.commit(gid))

    def test_buffered_value_plays_after_epoch_advance_naive(self):
        """F4 (naive): redeem succeeded at epoch 1; renderer buffers the value;
        epoch advances to 2; nothing stops playback of the buffered value.
        This window is UNFIXABLE at the kernel layer — it is the residual risk."""
        now, advance = make_clock()
        ctx = Context('house-a', 'priya', frozenset({'priya'}), 1,
                      100.0, True, True, True, 1)
        lease = Kernel.prepare(SECRET, ctx, now())
        advance(0.05)
        buffered_value = Kernel.redeem(lease, ctx, now())  # legit at epoch 1
        self.assertEqual(buffered_value, SECRET.value)
        # ... mom walks in, epoch -> 2, renderer never re-checks ...
        played = buffered_value  # no mechanism consults anything here
        self.assertEqual(played, SECRET.value,
                         'buffered value plays after invalidation: unfixable here')

    def test_guarded_playback_check_refuses_stale_segment(self):
        """F4 (guarded): segment bound to (epoch, seq, digest); after the epoch
        advances, authorize_playback refuses. The *renderer* must call this per
        chunk — the arbiter cannot reach into the speaker."""
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid = arb.prepare_grant(SECRET)
        advance(0.05)
        value, segment = arb.commit(gid)
        self.assertTrue(arb.authorize_playback(segment))
        arb.audience_changed({'priya', 'mom'})
        self.assertFalse(arb.authorize_playback(segment),
                         'stale-epoch segment must be refused')

    def test_withdraw_one_grant_kills_all_pending(self):
        """F5: no per-lease revoke primitive exists. Withdrawing grant A while
        grant B is legitimately pending forces an epoch bump — B dies too.
        The sledgehammer is the only hammer."""
        now, advance = make_clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', now)
        gid_a = arb.prepare_grant(SECRET)
        gid_b = arb.prepare_grant(SECRET)
        self.assertIsNotNone(gid_a)
        self.assertIsNotNone(gid_b)
        # Owner withdraws A. Kernel offers no lease-level revoke; the arbiter's
        # only surgical-ish tool is the epoch bump (blueprint §6 invalidation).
        arb.audience_changed({'priya'})  # epoch 1 -> 2, audience unchanged
        advance(0.05)
        self.assertIsNone(arb.commit(gid_a))
        self.assertIsNone(arb.commit(gid_b),
                          'epoch bump denies the innocent grant too: F5')

    def test_kernel_has_no_lease_revoke(self):
        """F5 pinned: capsules have revoke(); leases have no counterpart."""
        self.assertTrue(hasattr(Kernel, 'revoke'),
                        'capsule revoke exists')
        self.assertFalse(hasattr(Kernel, 'revoke_lease'),
                         'no lease-level revoke primitive exists')


if __name__ == '__main__':
    unittest.main(verbosity=2)
