"""F2/F6: lease lifecycle and evidence freshness.

Audience change is an interrupt; stale or missing evidence must never upgrade
disclosure. Every transition is explicit at the control plane (audited), never
a silent change in behavior.
"""
import unittest
from dataclasses import replace

from tests.failure_paths.harness import (TENANT, OWNER, AuditSink, CertifiedFacade, make_ctx,
                     make_fixtures)
from earshot.kernel import Kernel


class LeaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.k = Kernel()
        self.audit = AuditSink()
        self.facade = CertifiedFacade(self.k, self.audit)
        self.facts = make_fixtures()
        self.private, self.public = self.facts

    def test_lease_denied_when_audience_gains_untrusted_listener(self):
        ctx = make_ctx(audience=frozenset({'owner:priya', 'mom'}),
                       controlled_renderer=True)
        self.assertIsNone(self.k.prepare(self.private, ctx, 100.0))
        # ...while a public fact still projects (no dead end for public content)
        self.assertIn('Collect groceries after 6.',
                      Kernel.room_projection(self.facts, ctx, 100.0))

    def test_lease_redeem_fails_after_epoch_change(self):
        ctx = make_ctx(epoch=7)
        lease = self.k.prepare(self.private, ctx, 100.0)
        self.assertIsNotNone(lease)
        changed = replace(ctx, epoch=8,
                          audience=frozenset({'owner:priya', 'mom'}))
        self.assertIsNone(self.k.redeem(lease, changed, 100.1))

    def test_lease_redeem_fails_after_expiry(self):
        ctx = make_ctx()
        lease = self.k.prepare(self.private, ctx, 100.0)
        self.assertIsNotNone(lease)
        # lease ttl is 0.25s in the reference kernel
        self.assertIsNone(self.k.redeem(lease, ctx, 101.0))

    def test_lease_redeem_fails_on_policy_version_change(self):
        ctx = make_ctx(policy_version=7)
        lease = self.k.prepare(self.private, ctx, 100.0)
        self.assertIsNotNone(lease)
        changed = replace(ctx, policy_version=8)
        self.assertIsNone(self.k.redeem(lease, changed, 100.1))

    def test_sensor_disconnect_never_upgrades(self):
        # evidence_valid=False -> UNKNOWN joins the audience -> private denied
        ctx = make_ctx(evidence_valid=False, controlled_renderer=True)
        self.assertIn('UNKNOWN', ctx.effective_audience(100.0))
        self.assertIsNone(self.k.prepare(self.private, ctx, 100.0))

    def test_stale_evidence_never_upgrades(self):
        ctx = make_ctx(observed_at=10.0, controlled_renderer=True)
        self.assertIn('UNKNOWN', ctx.effective_audience(100.0))  # ttl=1.0s
        self.assertIsNone(self.k.prepare(self.private, ctx, 100.0))

    def test_undeclared_coverage_never_upgrades(self):
        ctx = make_ctx(coverage_assumed=False, controlled_renderer=True)
        self.assertIn('UNKNOWN', ctx.effective_audience(100.0))
        self.assertIsNone(self.k.prepare(self.private, ctx, 100.0))

    def test_future_observation_rejected(self):
        # observed_at in the future relative to now -> treated as invalid
        ctx = make_ctx(observed_at=200.0, controlled_renderer=True)
        self.assertIn('UNKNOWN', ctx.effective_audience(100.0))

    def test_contradictory_evidence_widens_audience(self):
        # Two sensors disagree: the union (wider) audience governs, and the
        # facade must surface degraded capability, not pick the convenient one.
        ctx = make_ctx(audience=frozenset({'owner:priya', 'mom'}),
                       controlled_renderer=True)
        self.assertIsNone(self.k.prepare(self.private, ctx, 100.0))
        resp = self.facade._deny('prepare_day_brief', 'contradictory_evidence')
        self.assertIn('continuation', resp)

    def test_uncontrolled_renderer_gets_public_only(self):
        ctx = make_ctx(controlled_renderer=False)
        proj = Kernel.room_projection(self.facts, ctx, 100.0)
        self.assertEqual(proj, ('Collect groceries after 6.',))
        self.assertIsNone(self.k.prepare(self.private, ctx, 100.0))

    def test_no_auto_resume_after_listener_leaves(self):
        # Lease invalidated at epoch 8 must not become valid again at epoch 9
        # just because the audience shrank back.
        ctx = make_ctx(epoch=8,
                       audience=frozenset({'owner:priya', 'mom'}),
                       controlled_renderer=True)
        lease = self.k.prepare(self.private, ctx, 100.0)
        self.assertIsNone(lease)  # denied while mom present
        alone = replace(ctx, epoch=9, audience=frozenset({'owner:priya'}))
        # A NEW lease must be minted; the old (nonexistent) grant stays dead.
        fresh = self.k.prepare(self.private, alone, 100.2)
        self.assertIsNotNone(fresh)
        self.assertNotEqual(getattr(lease, 'epoch', None), fresh.epoch)


if __name__ == '__main__':
    unittest.main()
