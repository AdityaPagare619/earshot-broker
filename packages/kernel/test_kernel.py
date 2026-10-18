import unittest
from dataclasses import replace
from itertools import combinations
from kernel import Context, Fact, Kernel, Label

PUB = Label(frozenset({'*'}))
PRI = Label(frozenset({'priya'}), frozenset({'health'}))
FAMILY = Label(frozenset({'priya', 'ravi'}), frozenset({'family'}))
PUBLIC_FACT = Fact('weather', 'Rain is forecast.', PUB)
SECRET = Fact('appointment', 'Prenatal visit, 15:40', PRI)
CTX = Context('house-a', 'priya', frozenset({'priya'}), 1, 100.0,
              True, True, True, 1)

class KernelTests(unittest.TestCase):
    def test_public_host_never_gets_private_fact_even_alone(self):
        self.assertEqual(Kernel.room_projection((PUBLIC_FACT, SECRET),
                         replace(CTX, controlled_renderer=False), 100),
                         ('Rain is forecast.',))
    def test_controlled_host_can_release_under_explicit_assumptions(self):
        self.assertEqual(Kernel.room_projection((SECRET,), CTX, 100), (SECRET.value,))
    def test_unknown_denies_private(self):
        self.assertEqual(Kernel.room_projection((SECRET,), replace(CTX, evidence_valid=False), 100), ())
    def test_stale_denies_private(self):
        self.assertEqual(Kernel.room_projection((SECRET,), CTX, 102), ())
    def test_missing_coverage_denies_private(self):
        self.assertEqual(Kernel.room_projection((SECRET,), replace(CTX, coverage_assumed=False), 100), ())
    def test_clock_regression_denies_private(self):
        self.assertEqual(Kernel.room_projection((SECRET,), CTX, 99), ())
    def test_mother_entered_invalidates_lease(self):
        lease = Kernel.prepare(SECRET, CTX, 100)
        changed = replace(CTX, audience=frozenset({'priya', 'mom'}), epoch=2)
        self.assertIsNone(Kernel.redeem(lease, changed, 100.1))
    def test_epoch_change_without_audience_change_still_invalidates(self):
        self.assertIsNone(Kernel.redeem(Kernel.prepare(SECRET, CTX, 100), replace(CTX, epoch=2), 100.1))
    def test_policy_change_invalidates(self):
        self.assertIsNone(Kernel.redeem(Kernel.prepare(SECRET, CTX, 100), replace(CTX, policy_version=2), 100.1))
    def test_expiry_invalidates(self):
        self.assertIsNone(Kernel.redeem(Kernel.prepare(SECRET, CTX, 100), CTX, 100.25))
    def test_identity_change_invalidates(self):
        self.assertIsNone(Kernel.redeem(Kernel.prepare(SECRET, CTX, 100), replace(CTX, principal='mom'), 100.1))
    def test_valid_commit(self):
        self.assertEqual(Kernel.redeem(Kernel.prepare(SECRET, CTX, 100), CTX, 100.1), SECRET.value)
    def test_uncontrolled_cannot_issue_lease(self):
        self.assertIsNone(Kernel.prepare(SECRET, replace(CTX, controlled_renderer=False), 100))
    def test_taint_of_derived_result(self):
        d = Kernel.derive('leave_by', 'Leave at 15:00', (PUBLIC_FACT, SECRET))
        self.assertEqual(d.label, PRI)
    def test_reader_intersection(self):
        self.assertEqual(PRI.join(FAMILY).readers, frozenset({'priya'}))
    def test_refuse_unproven_dependency_free_derivation(self):
        with self.assertRaises(ValueError): Kernel.derive('x', 'safe', ())
    def test_secret_rename_and_existence_do_not_change_public_projection(self):
        for secret in [(), (SECRET,), (replace(SECRET, value='Oncology'),), (SECRET, SECRET)]:
            self.assertEqual(Kernel.public_projection((PUBLIC_FACT,) + secret), ('Rain is forecast.',))
    def test_receipt_shape_independent_of_private_result(self):
        shapes = []
        for facts in [(), (SECRET,), (SECRET, SECRET)]:
            out = Kernel().accept('house-a', 'priya', 'request', facts, 100)
            out.pop('receipt')
            shapes.append(out)
        self.assertEqual(shapes[0], shapes[1]); self.assertEqual(shapes[1], shapes[2])
    def test_idempotent_accept(self):
        k = Kernel()
        a = k.accept('house-a', 'priya', 'request', (SECRET,), 100)
        self.assertEqual(a, k.accept('house-a', 'priya', 'request', (SECRET,), 101))
    def test_handle_is_not_authorization(self):
        k = Kernel(); r = k.accept('house-a', 'priya', 'r', (SECRET,), 100)['receipt']
        for tenant, user, auth in [('house-a', 'mom', True), ('house-b', 'priya', True), ('house-a', 'priya', False)]:
            with self.assertRaises(PermissionError): k.open_private(r, tenant, user, auth, 101)
    def test_owner_can_open(self):
        k = Kernel(); r = k.accept('house-a', 'priya', 'r', (SECRET,), 100)['receipt']
        self.assertEqual(k.open_private(r, 'house-a', 'priya', True, 101), (SECRET,))
    def test_expired_capsule(self):
        k = Kernel(); r = k.accept('house-a', 'priya', 'r', (SECRET,), 100)['receipt']
        with self.assertRaises(PermissionError): k.open_private(r, 'house-a', 'priya', True, 400)
    def test_revoked_capsule(self):
        k = Kernel(); r = k.accept('house-a', 'priya', 'r', (SECRET,), 100)['receipt']
        k.revoke(r, 'house-a', 'priya')
        with self.assertRaises(PermissionError): k.open_private(r, 'house-a', 'priya', True, 101)
    def test_finite_audience_monotonicity(self):
        people = ('priya', 'ravi', 'mom', 'UNKNOWN')
        sets = [frozenset(c) for n in range(5) for c in combinations(people, n)]
        facts = (PUBLIC_FACT, SECRET, Fact('dinner', 'Dinner at 7', FAMILY))
        for a in sets:
            for b in sets:
                if a <= b:
                    out_a = set(Kernel.room_projection(facts, replace(CTX, audience=a), 100))
                    out_b = set(Kernel.room_projection(facts, replace(CTX, audience=b), 100))
                    self.assertTrue(out_b <= out_a)

if __name__ == '__main__': unittest.main(verbosity=2)
