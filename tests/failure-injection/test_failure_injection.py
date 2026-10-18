"""Failure injection: each named fault vs the kernel's actual response.

Deterministic and reproducible — every fault is applied at a precise boundary
and the response is asserted, not observed-and-hoped.
"""
import unittest
from dataclasses import replace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'packages', 'kernel'))
from kernel import Context, Fact, Kernel, Label  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'races'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arbiter import Arbiter  # noqa: E402
from faults import (Clock, SkewedClock, kill_sensor, forge_observed_at,
                    tenant_confusion, timeout_after_accept,
                    incomplete_derive)  # noqa: E402

PRI = Label(frozenset({'priya'}), frozenset({'health'}))
SECRET = Fact('appointment', 'Prenatal visit, 15:40', PRI)
SECRET_V2 = Fact('appointment', 'Prenatal visit, RESCHEDULED 16:20', PRI)
PUB = Label(frozenset({'*'}))
PUBLIC_FACT = Fact('weather', 'Rain is forecast.', PUB)


def ctx_at(clock, **kw):
    base = dict(tenant='house-a', principal='priya',
                audience=frozenset({'priya'}), epoch=1,
                observed_at=clock.now(), evidence_valid=True,
                coverage_assumed=True, controlled_renderer=True,
                policy_version=1)
    base.update(kw)
    return Context(**base)


class FailureInjection(unittest.TestCase):
    # -- F2: the clock -------------------------------------------------------
    def test_frozen_clock_defeats_lease_expiry(self):
        """F2 severe: renderer pins now at issue time; the 0.25s lease TTL
        never expires from the kernel's view. Unfixable in-kernel."""
        clock = Clock()
        ctx = ctx_at(clock)
        lease = Kernel.prepare(SECRET, ctx, clock.now())
        frozen = SkewedClock(clock, frozen_at=100.1)
        clock.advance(3600)  # an hour passes in reality
        # Renderer keeps presenting now=100.1: kernel still releases.
        self.assertEqual(Kernel.redeem(lease, ctx, frozen.now()), SECRET.value)

    def test_frozen_clock_defeats_sensor_ttl(self):
        """F2 severe: frozen now also defeats the 1.0s evidence TTL."""
        clock = Clock()
        stale = ctx_at(clock, observed_at=50.0)  # 50s old evidence
        frozen = SkewedClock(clock, frozen_at=50.5)
        out = Kernel.room_projection((SECRET,), stale, frozen.now())
        self.assertIn(SECRET.value, out,
                      'frozen clock makes 50s-old evidence look fresh')

    def test_skewed_clock_small_drift_within_ttl(self):
        """Small skew inside TTL windows behaves like an honest clock —
        the finding is about *who* controls the clock, not the drift size."""
        clock = Clock()
        skewed = SkewedClock(clock, skew=0.1)
        ctx = ctx_at(clock)
        lease = Kernel.prepare(SECRET, ctx, skewed.now())
        self.assertIsNotNone(lease)

    def test_clock_regression_denied(self):
        """Good behavior: now < observed_at is rejected (kernel's own test,
        re-pinned here as the honest-clock control)."""
        clock = Clock()
        ctx = ctx_at(clock)
        out = Kernel.room_projection((SECRET,), ctx, clock.now() - 1)
        self.assertEqual(out, ())

    # -- F3: stale accept ----------------------------------------------------
    def test_timeout_after_accept_serves_stale_facts(self):
        """F3: same request_key, revised facts -> old capsule wins.
        The continuation opens plan v1 although v2 was accepted."""
        k = Kernel()
        clock = Clock()
        first, second = timeout_after_accept(
            k, 'house-a', 'priya', 'day-brief', (SECRET,), (SECRET_V2,),
            clock.now())
        self.assertEqual(first['receipt'], second['receipt'],
                         'idempotent: same key, same receipt')
        opened = k.open_private(first['receipt'], 'house-a', 'priya', True,
                                clock.now())
        self.assertEqual(opened, (SECRET,),
                         'capsule holds v1 facts: v2 silently lost')

    # -- F7: sensor faults ---------------------------------------------------
    def test_kill_sensor_mid_lease_denies(self):
        clock = Clock()
        ctx = ctx_at(clock)
        lease = Kernel.prepare(SECRET, ctx, clock.now())
        clock.advance(0.05)
        dead = kill_sensor(ctx)
        self.assertIsNone(Kernel.redeem(lease, dead, clock.now()))

    def test_forged_observed_at_passes(self):
        """F7: sensor dead since t=90, timestamp forged to 99.9 — kernel
        releases. The check that would catch this lives outside the kernel."""
        clock = Clock()
        ctx = ctx_at(clock)
        forged = forge_observed_at(ctx, 99.9)
        clock.advance(0.05)
        lease = Kernel.prepare(SECRET, forged, clock.now())
        self.assertIsNotNone(lease, 'forged freshness passes prepare')
        self.assertEqual(Kernel.redeem(lease, forged, clock.now()),
                         SECRET.value)

    # -- crash mid-flight ----------------------------------------------------
    def test_crash_between_prepare_and_commit_leaves_nothing(self):
        """Bearer leases are crash-safe: renderer drops all local state
        after prepare; nothing was persisted server-side, so a restart
        cannot half-commit. (Arbiter grants are swept on expiry.)"""
        clock = Clock()
        arb = Arbiter('house-a', 'priya', 'kitchen', clock.now)
        gid = arb.prepare_grant(SECRET)
        self.assertIsNotNone(gid)
        # --- renderer crashes: gid lost, process restarts ---
        restarted_renderer_knows = []
        self.assertEqual(restarted_renderer_knows, [])
        # Grant lingers server-side until TTL sweep — then it's gone.
        clock.advance(10.0)
        swept = arb.sweep_expired()
        self.assertIn(gid, swept)
        self.assertEqual(arb.pending_grants(), [])

    def test_revoke_capsule_midflight(self):
        """withdraw_request analogue: revoke between accept and open ->
        PermissionError, one generic message (no oracle)."""
        k = Kernel()
        clock = Clock()
        r = k.accept('house-a', 'priya', 'r', (SECRET,), clock.now())['receipt']
        k.revoke(r, 'house-a', 'priya')
        with self.assertRaises(PermissionError) as cm:
            k.open_private(r, 'house-a', 'priya', True, clock.now())
        self.assertEqual(str(cm.exception), 'Unavailable')

    # -- F8: dependency omission ----------------------------------------------
    def test_incomplete_derive_launders_label(self):
        """F8: value computed from SECRET but declared deps omit it ->
        derived fact labeled PUBLIC. Label propagation trusts the caller."""
        laundered = incomplete_derive('leave_by', 'Leave at 15:00',
                                      (PUBLIC_FACT,))
        self.assertEqual(laundered.label, PUB,
                         'omitted secret dependency -> PUBLIC label')
        # The PUBLIC-labeled value now crosses any projection:
        out = Kernel.public_projection((laundered,))
        self.assertIn('Leave at 15:00', out)

    def test_honest_derive_taints(self):
        """Control: declared deps including the secret taint correctly."""
        d = Kernel.derive('leave_by', 'Leave at 15:00', (PUBLIC_FACT, SECRET))
        self.assertEqual(d.label.readers, frozenset({'priya'}))

    # -- F9: tenant confusion --------------------------------------------------
    def test_tenant_confusion_at_redeem_denied(self):
        """Renderer mixes up tenants: lease is house-a, ctx says house-b."""
        clock = Clock()
        ctx = ctx_at(clock)
        lease = Kernel.prepare(SECRET, ctx, clock.now())
        confused = tenant_confusion(ctx, 'house-b')
        clock.advance(0.05)
        self.assertIsNone(Kernel.redeem(lease, confused, clock.now()))

    def test_same_principal_name_across_tenants_isolated(self):
        """'priya' in house-b cannot open house-a's capsule (kernel's own
        guarantee, re-pinned as the adversarial control)."""
        k = Kernel()
        clock = Clock()
        r = k.accept('house-a', 'priya', 'r', (SECRET,), clock.now())['receipt']
        with self.assertRaises(PermissionError):
            k.open_private(r, 'house-b', 'priya', True, clock.now())


if __name__ == '__main__':
    unittest.main(verbosity=2)
