"""F1/F2: error-oracle indistinguishability.

Certification requirement: error responses must not let a caller distinguish
"unknown" from "revoked" from "expired" from "wrong tenant" from
"unauthenticated" — and must never carry secret bytes. Every denial renders
the identical public shape.
"""
import unittest

from harness import (SECRET_STRINGS, TENANT, OWNER, AuditSink, CertifiedFacade,
                     make_fixtures)
from kernel import Kernel


def collect_public_strings(facade, kernel, receipt_known):
    """Harvest every public string the facade and kernel can emit on denials."""
    out = []
    # facade-level denials, every cause
    out.append(facade.prepare_day_brief(TENANT, OWNER, 'not-a-date',
                                        'Asia/Kolkata', 'k' * 16,
                                        make_fixtures(), 100.0))
    out.append(facade.prepare_day_brief(TENANT, OWNER, '2026-10-20',
                                        'Mars/Olympus', 'k' * 16,
                                        make_fixtures(), 100.0))
    out.append(facade.prepare_day_brief(TENANT, OWNER, '2026-10-20',
                                        'Asia/Kolkata', 'short',
                                        make_fixtures(), 100.0))
    out.append(facade.resolve_day_change(TENANT, OWNER, 'no-such-ref',
                                         make_fixtures(), 100.0))
    out.append(facade.continue_on_personal_device(TENANT, OWNER, 'no-such-ref',
                                                  100.0))
    out.append(facade.withdraw_request(TENANT, OWNER, 'no-such-ref', 100.0))
    # kernel-level denials: capture exception messages
    for fn in (
        lambda: kernel.open_private('no-such-receipt', TENANT, OWNER, True, 100.0),
        lambda: kernel.open_private(receipt_known, TENANT, OWNER, False, 100.0),
        lambda: kernel.open_private(receipt_known, 'tenant:other', OWNER, True, 100.0),
        lambda: kernel.open_private(receipt_known, TENANT, 'owner:mallory', True, 100.0),
        lambda: kernel.open_private(receipt_known, TENANT, OWNER, True, 99999.0),
        lambda: kernel.revoke('no-such-receipt', TENANT, OWNER),
        lambda: kernel.revoke(receipt_known, 'tenant:other', OWNER),
    ):
        try:
            fn()
            out.append('NO-ERROR-RAISED')
        except PermissionError as e:
            out.append(str(e))
    return out


class ErrorOracleTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel()
        self.audit = AuditSink()
        self.facade = CertifiedFacade(self.kernel, self.audit)
        self.facts = make_fixtures()
        r = self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-20',
                                          'Asia/Kolkata', 'k' * 20,
                                          self.facts, 100.0)
        self.receipt = r['request_ref']

    def _flatten(self, obj):
        if isinstance(obj, dict):
            for v in obj.values():
                yield from self._flatten(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                yield from self._flatten(v)
        elif isinstance(obj, str):
            yield obj

    def test_no_secret_bytes_anywhere_public(self):
        for item in collect_public_strings(self.facade, self.kernel, self.receipt):
            for s in self._flatten(item):
                for secret in SECRET_STRINGS:
                    self.assertNotIn(secret, s,
                                     f'secret {secret!r} leaked in public output: {s!r}')

    def test_kernel_denials_identical(self):
        """Unknown / revoked / expired / wrong-tenant / unauthenticated are
        indistinguishable at the kernel boundary."""
        msgs = set()
        # revoke the known receipt first, then try to open it
        self.kernel.revoke(self.receipt, TENANT, OWNER)
        cases = [
            lambda: self.kernel.open_private('no-such-receipt', TENANT, OWNER, True, 100.0),
            lambda: self.kernel.open_private(self.receipt, TENANT, OWNER, True, 100.0),  # revoked
            lambda: self.kernel.open_private(self.receipt, TENANT, OWNER, False, 100.0),  # unauth
            lambda: self.kernel.open_private(self.receipt, 'tenant:x', OWNER, True, 100.0),
            lambda: self.kernel.open_private(self.receipt, TENANT, 'owner:x', True, 100.0),
        ]
        for fn in cases:
            with self.assertRaises(PermissionError) as cm:
                fn()
            msgs.add(str(cm.exception))
        self.assertEqual(len(msgs), 1,
                         f'denial messages distinguishable: {msgs}')

    def test_facade_denial_shapes_identical_per_tool(self):
        """Same key set on every denial response of a tool (C1)."""
        denies = [
            self.facade.prepare_day_brief(TENANT, OWNER, 'bad', 'Asia/Kolkata',
                                          'k' * 16, self.facts, 100.0),
            self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Bad/Zone',
                                          'k' * 16, self.facts, 100.0),
            self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-20',
                                          'Asia/Kolkata', 'x', self.facts, 100.0),
        ]
        shapes = {tuple(sorted(d.keys())) for d in denies}
        self.assertEqual(len(shapes), 1, f'denial shapes differ: {shapes}')
        # and identical to a *successful* shape's key set (no shape oracle)
        ok = self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-21',
                                           'Asia/Kolkata', 'k' * 21,
                                           self.facts, 100.0)
        self.assertEqual(set(denies[0].keys()) - {'request_ref'},
                         set(ok.keys()) - {'request_ref'})

    def test_receipts_are_random_and_opaque(self):
        r1 = self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-22',
                                           'Asia/Kolkata', 'k' * 22,
                                           self.facts, 100.0)['request_ref']
        r2 = self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-23',
                                           'Asia/Kolkata', 'k' * 23,
                                           self.facts, 100.0)['request_ref']
        self.assertNotEqual(r1, r2)
        for secret in SECRET_STRINGS:
            self.assertNotIn(secret, r1)
            self.assertNotIn(secret, r2)

    def test_audit_records_real_cause_control_plane_only(self):
        """The control plane knows the cause; the public surface does not."""
        self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Bad/Zone',
                                      'k' * 24, self.facts, 100.0)
        self.assertIn('invalid_timezone', self.audit.causes('prepare_day_brief'))
        # ...but the public response carries no cause
        resp = self.facade.prepare_day_brief(TENANT, OWNER, '2026-10-20',
                                             'Bad/Zone', 'k' * 25,
                                             self.facts, 100.0)
        flat = ' '.join(self._flatten(resp))
        self.assertNotIn('invalid_timezone', flat)
        self.assertNotIn('timezone', flat.lower())


if __name__ == '__main__':
    unittest.main()
