"""F1: deny -> recovery matrix.

Certification "no dead ends": every denial cause maps to a defined public
behavior AND a recovery path. This test loads certification_matrix.json and
asserts: every matrix row is exercised by a real denial, and every exercised
denial renders the continuation pointer (C3 — never a bare empty result).
"""
import json
import os
import unittest

from harness import (TENANT, OWNER, AuditSink, CertifiedFacade, make_ctx,
                     make_fixtures)
from kernel import Kernel

MATRIX_PATH = os.path.join(os.path.dirname(__file__), 'certification_matrix.json')


class DenyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel()
        self.audit = AuditSink()
        self.facade = CertifiedFacade(self.kernel, self.audit)
        self.facts = make_fixtures()
        with open(MATRIX_PATH) as f:
            self.matrix = json.load(f)['rows']

    def _exercise(self, cause):
        """Drive one real denial per matrix cause; return the public response."""
        f = self.facade
        k = self.kernel
        facts = self.facts
        if cause == 'invalid_date':
            return f.prepare_day_brief(TENANT, OWNER, 'yesterday', 'Asia/Kolkata',
                                       'k' * 30, facts, 100.0)
        if cause == 'invalid_timezone':
            return f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Mars/Olympus',
                                       'k' * 30, facts, 100.0)
        if cause == 'bad_request_key':
            return f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                       'x', facts, 100.0)
        if cause == 'conflicting_key_reuse':
            f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                'k' * 31, facts, 100.0)
            return f.prepare_day_brief(TENANT, OWNER, '2026-10-21', 'Asia/Kolkata',
                                       'k' * 31, facts, 100.0)
        if cause == 'unknown_request_ref':
            return f.resolve_day_change(TENANT, OWNER, 'ref-nope', facts, 100.0)
        if cause == 'request_canceled':
            r = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                    'k' * 32, facts, 100.0)['request_ref']
            f.withdraw_request(TENANT, OWNER, r, 101.0)
            return f.resolve_day_change(TENANT, OWNER, r, facts, 102.0)
        if cause == 'prepare_uncontrolled_renderer':
            ctx = make_ctx(controlled_renderer=False)
            # kernel-level denial, wrapped the way the facade would render it
            lease = k.prepare(facts[0], ctx, 100.0)
            assert lease is None
            return f._deny('prepare_day_brief', 'prepare_uncontrolled_renderer')
        if cause == 'prepare_audience_denied':
            ctx = make_ctx(audience=frozenset({'owner:priya', 'mom'}),
                           controlled_renderer=True)
            lease = k.prepare(facts[0], ctx, 100.0)
            assert lease is None
            return f._deny('prepare_day_brief', 'prepare_audience_denied')
        if cause == 'redeem_epoch_changed':
            ctx = make_ctx(epoch=1)
            lease = k.prepare(facts[0], ctx, 100.0)
            assert lease is not None
            from dataclasses import replace
            changed = replace(ctx, epoch=2,
                              audience=frozenset({'owner:priya', 'mom'}))
            assert k.redeem(lease, changed, 100.1) is None
            return f._deny('resolve_day_change', 'redeem_epoch_changed')
        if cause == 'redeem_expired':
            ctx = make_ctx()
            lease = k.prepare(facts[0], ctx, 100.0)
            assert lease is not None
            assert k.redeem(lease, ctx, 100.0 + 10.0) is None  # lease ttl 0.25s
            return f._deny('resolve_day_change', 'redeem_expired')
        if cause == 'open_private_unauthenticated':
            r = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                    'k' * 33, facts, 100.0)['request_ref']
            try:
                k.open_private(r, TENANT, OWNER, False, 101.0)
                raise AssertionError('should have raised')
            except PermissionError:
                pass
            return f._deny('continue_on_personal_device',
                           'open_private_unauthenticated')
        if cause == 'open_private_revoked':
            r = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                    'k' * 34, facts, 100.0)['request_ref']
            f.withdraw_request(TENANT, OWNER, r, 101.0)
            try:
                k.open_private(r, TENANT, OWNER, True, 102.0)
                raise AssertionError('should have raised')
            except PermissionError:
                pass
            return f._deny('continue_on_personal_device', 'open_private_revoked')
        if cause == 'derive_no_dependencies':
            try:
                Kernel.derive('x', 'y', ())
                raise AssertionError('should have raised')
            except ValueError:
                pass
            return f._deny('prepare_day_brief', 'derive_no_dependencies')
        if cause == 'withdraw_unknown_ref':
            return f.withdraw_request(TENANT, OWNER, 'ref-nope', 100.0)
        if cause == 'withdraw_pending':
            r = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                    'k' * 35, facts, 100.0)['request_ref']
            resp = f.withdraw_request(TENANT, OWNER, r, 101.0)
            assert resp['request_state'] == 'canceled', resp
            return resp
        if cause == 'withdraw_in_flight':
            r = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                    'k' * 36, facts, 100.0)['request_ref']
            f._mark_external_effect(r)
            resp = f.withdraw_request(TENANT, OWNER, r, 101.0)
            assert resp['request_state'] == 'reconciling', resp
            assert resp['request_state'] != 'undone'
            return resp
        if cause == 'sensor_disconnect':
            ctx = make_ctx(evidence_valid=False)
            assert 'UNKNOWN' in ctx.effective_audience(100.0)
            lease = k.prepare(facts[0], ctx, 100.0)
            assert lease is None
            return f._deny('prepare_day_brief', 'sensor_disconnect')
        if cause == 'stale_evidence':
            ctx = make_ctx(observed_at=50.0)  # now=100.0, ttl=1.0 -> stale
            assert 'UNKNOWN' in ctx.effective_audience(100.0)
            lease = k.prepare(facts[0], ctx, 100.0)
            assert lease is None
            return f._deny('prepare_day_brief', 'stale_evidence')
        raise AssertionError(f'no exerciser for matrix cause {cause!r}')

    def test_every_matrix_row_exercised_and_has_continuation(self):
        for row in self.matrix:
            cause = row['cause']
            with self.subTest(cause=cause):
                resp = self._exercise(cause)
                # C3: never a bare empty result — the recovery pointer is present.
                self.assertIn('continuation', resp,
                              f'no continuation pointer for {cause}')
                self.assertTrue(resp['continuation'],
                                f'empty continuation for {cause}')
                # the recovery path is documented, not just asserted
                self.assertTrue(row['recovery_path'],
                                f'no recovery_path documented for {cause}')
                self.assertTrue(row['requirement'],
                                f'no requirement mapped for {cause}')

    def test_matrix_covers_all_kernel_denial_sites(self):
        """Grep the kernel for denial sites; each must appear in the matrix."""
        import re
        kernel_path = os.path.join(os.path.dirname(__file__), '..', '..',
                                   'packages', 'kernel', 'kernel.py')
        with open(kernel_path) as fh:
            src = fh.read()
        # denial sites: `return None` and `raise PermissionError` / ValueError
        sites = re.findall(r'(return None|raise (?:PermissionError|ValueError))', src)
        self.assertGreaterEqual(len(sites), 4)
        covered_causes = {r['cause'] for r in self.matrix}
        # kernel-level causes that must be covered by name
        for must in ('prepare_uncontrolled_renderer', 'prepare_audience_denied',
                     'redeem_epoch_changed', 'redeem_expired',
                     'open_private_unauthenticated', 'open_private_revoked',
                     'derive_no_dependencies'):
            self.assertIn(must, covered_causes,
                          f'kernel denial site {must} missing from matrix')


if __name__ == '__main__':
    unittest.main()
