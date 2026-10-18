"""Adversarial inputs: garbage and hostile values at the trust boundary.

Every case asserts the kernel's *actual* response — including the ones where
the response is "allows", so the behavior is pinned and reviewable rather
than accidental.
"""
import unittest
from dataclasses import replace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'packages', 'kernel'))
from kernel import Context, Fact, Kernel, Label  # noqa: E402

PRI = Label(frozenset({'priya'}), frozenset({'health'}))
SECRET = Fact('appointment', 'Prenatal visit, 15:40', PRI)
PUB = Label(frozenset({'*'}))
PUBLIC_FACT = Fact('weather', 'Rain is forecast.', PUB)


def base_ctx(**kw):
    d = dict(tenant='house-a', principal='priya',
             audience=frozenset({'priya'}), epoch=1, observed_at=100.0,
             evidence_valid=True, coverage_assumed=True,
             controlled_renderer=True, policy_version=1)
    d.update(kw)
    return Context(**d)


class AdversarialInputs(unittest.TestCase):
    def test_receipt_guessing_gives_no_oracle(self):
        """Wrong receipt -> same generic PermissionError as expired/revoked.
        No existence oracle, no timing oracle asserted here (out of scope)."""
        k = Kernel()
        for bad in ['nope', '', 'a' * 43]:
            with self.assertRaises(PermissionError) as cm:
                k.open_private(bad, 'house-a', 'priya', True, 100)
            self.assertEqual(str(cm.exception), 'Unavailable')

    def test_attacker_cannot_flip_controlled_renderer(self):
        """The flag lives in the Context the *arbiter* mints. An attacker
        flipping it in a self-minted context gets nothing: prepare returns
        None for uncontrolled renderers."""
        evil = base_ctx(controlled_renderer=False)
        self.assertIsNone(Kernel.prepare(SECRET, evil, 100))
        self.assertEqual(Kernel.room_projection((SECRET,), evil, 100), ())

    def test_audience_only_unknown_denies(self):
        ctx = base_ctx(audience=frozenset({'UNKNOWN'}))
        self.assertEqual(Kernel.room_projection((SECRET,), ctx, 100), ())

    def test_empty_readers_label(self):
        """Label(readers=frozenset()): releasable only to the empty audience.
        Pinned — an 'allow-nobody' label degrades to 'allow-empty-room'."""
        nobody = Label(frozenset())
        fact = Fact('x', 'v', nobody)
        self.assertEqual(Kernel.room_projection((fact,), base_ctx(), 100), ())
        empty_room = base_ctx(audience=frozenset())
        self.assertIn('v', Kernel.room_projection((fact,), empty_room, 100))

    def test_garbage_epoch_and_policy_version(self):
        """Nonsense versions don't fail open: redeem compares for equality
        against the lease's own versions, so garbage mismatches deny."""
        lease = Kernel.prepare(SECRET, base_ctx(), 100)
        weird = base_ctx(epoch=-1, policy_version=0)
        self.assertIsNone(Kernel.redeem(lease, weird, 100.1))

    def test_audience_superset_with_stranger_denies(self):
        """One extra listener the label doesn't know -> subset fails -> deny."""
        ctx = base_ctx(audience=frozenset({'priya', 'stranger'}))
        self.assertEqual(Kernel.room_projection((SECRET,), ctx, 100), ())

    def test_label_allows_is_exact_subset(self):
        """Readers {'priya','ravi'} with audience {'priya'}: subset holds ->
        allowed. Pinned: being *in* the readers set is sufficient."""
        fam = Label(frozenset({'priya', 'ravi'}))
        fact = Fact('d', 'Dinner at 7', fam)
        out = Kernel.room_projection((fact,), base_ctx(), 100)
        self.assertIn('Dinner at 7', out)

    def test_empty_string_tenant_isolated(self):
        """Degenerate tenant '' works but is isolated from 'house-a'."""
        k = Kernel()
        r = k.accept('', 'priya', 'r', (SECRET,), 100)['receipt']
        with self.assertRaises(PermissionError):
            k.open_private(r, 'house-a', 'priya', True, 100)
        self.assertEqual(k.open_private(r, '', 'priya', True, 100), (SECRET,))

    def test_lease_bound_to_fact_label_at_redeem(self):
        """redeem re-checks the *lease's* label against the current audience —
        a label can't be swapped between prepare and redeem (Fact is frozen)."""
        lease = Kernel.prepare(SECRET, base_ctx(), 100)
        # Attacker can't mutate the frozen lease; redeem against a room that
        # gained an untrusted listener denies via the label check too.
        changed = base_ctx(audience=frozenset({'priya', 'mom'}), epoch=1)
        self.assertIsNone(Kernel.redeem(lease, changed, 100.1))

    def test_public_fact_always_crosses(self):
        """PUBLIC facts cross even to uncontrolled hosts and dead sensors —
        by design; PUBLIC means public."""
        dead = base_ctx(evidence_valid=False, controlled_renderer=False)
        self.assertEqual(Kernel.room_projection((PUBLIC_FACT, SECRET), dead, 100),
                         ('Rain is forecast.',))


if __name__ == '__main__':
    unittest.main(verbosity=2)
