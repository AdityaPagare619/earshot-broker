"""F5/F7: withdraw vs reconcile; cancellation is not undo.

Dossier decisions 58-59: withdraw_request stops queued work and future
disclosures. It cannot retract a sent email, undo a delivered notification, or
un-speak a sentence. The public surface must never report 'undone' for an
external effect; exact state is private.
"""
import unittest

from tests.failure_paths.harness import (TENANT, OWNER, AuditSink, CertifiedFacade, make_fixtures)
from earshot.kernel import Kernel


class WithdrawReconcileTests(unittest.TestCase):
    def setUp(self):
        self.k = Kernel()
        self.audit = AuditSink()
        self.facade = CertifiedFacade(self.k, self.audit)
        self.facts = make_fixtures()

    def _prepare(self, key):
        return self.facade.prepare_day_brief(
            TENANT, OWNER, '2026-10-20', 'Asia/Kolkata', key,
            self.facts, 100.0)['request_ref']

    def test_withdraw_pending_cancels(self):
        ref = self._prepare('k' * 40)
        resp = self.facade.withdraw_request(TENANT, OWNER, ref, 101.0)
        self.assertEqual(resp['request_state'], 'canceled')
        self.assertIn('continuation', resp)

    def test_withdraw_in_flight_reports_reconciling_never_undone(self):
        ref = self._prepare('k' * 41)
        self.facade._mark_external_effect(ref)
        resp = self.facade.withdraw_request(TENANT, OWNER, ref, 101.0)
        self.assertEqual(resp['request_state'], 'reconciling')
        flat = ' '.join(str(v) for v in resp.values())
        self.assertNotIn('undone', flat.lower())
        self.assertNotIn('complete', flat.lower())

    def test_withdraw_unknown_ref_is_opaque(self):
        resp = self.facade.withdraw_request(TENANT, OWNER, 'ref-nope', 100.0)
        self.assertIn('continuation', resp)
        # identical key set to a successful withdraw (no shape oracle)
        ref = self._prepare('k' * 42)
        ok = self.facade.withdraw_request(TENANT, OWNER, ref, 101.0)
        self.assertEqual(set(resp.keys()), set(ok.keys()))

    def test_withdraw_revokes_private_access(self):
        ref = self._prepare('k' * 43)
        self.facade.withdraw_request(TENANT, OWNER, ref, 101.0)
        with self.assertRaises(PermissionError):
            self.k.open_private(ref, TENANT, OWNER, True, 102.0)

    def test_double_withdraw_is_stable(self):
        ref = self._prepare('k' * 44)
        r1 = self.facade.withdraw_request(TENANT, OWNER, ref, 101.0)
        r2 = self.facade.withdraw_request(TENANT, OWNER, ref, 102.0)
        self.assertEqual(r1['request_state'], r2['request_state'])

    def test_canceled_request_cannot_be_resolved(self):
        ref = self._prepare('k' * 45)
        self.facade.withdraw_request(TENANT, OWNER, ref, 101.0)
        resp = self.facade.resolve_day_change(TENANT, OWNER, ref, self.facts, 102.0)
        self.assertIn('continuation', resp)
        # audit shows the real cause control-plane-side
        self.assertIn('request_canceled',
                      self.audit.causes('resolve_day_change'))


if __name__ == '__main__':
    unittest.main()
