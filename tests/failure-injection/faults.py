"""Deterministic fault injector.

Each fault is a named, reproducible scenario applied at a precise
prepare/redeem boundary — no random chaos. Every fault maps 1:1 to a verdict
finding (F1–F10) and its test asserts the kernel's actual response.

Faults are honest about what they model:
  kill_sensor()        -> evidence_valid flips False mid-flight (F7 signal path)
  skew_clock(dt)       -> renderer-controlled clock drifts (F2)
  freeze_clock()       -> renderer pins `now` at lease-issue time (F2, severe)
  bump_policy(arb)     -> policy_version increments mid-plan
  forge_observed_at()  -> Context minted with a lying timestamp (F7)
  crash_renderer()     -> local state dropped between prepare and commit
  timeout_after_accept -> upstream returns v2 facts for an accepted v1 key (F3)
  tenant_confusion()   -> cross-tenant context presented at redeem (F9)
  incomplete_derive()  -> planner omits a secret dependency (F8)
"""
from dataclasses import replace

import sys, os
from earshot.kernel import Context, Fact, Kernel, Label  # noqa: E402


class Clock:
    """Test-controlled clock; the arbiter's trusted time source."""
    def __init__(self, t=100.0):
        self.t = t
    def now(self):
        return self.t
    def advance(self, dt):
        self.t += dt


class SkewedClock:
    """A renderer-controlled clock: the F2 adversary."""
    def __init__(self, base, skew=0.0, frozen_at=None):
        self.base = base
        self.skew = skew
        self.frozen_at = frozen_at
    def now(self):
        if self.frozen_at is not None:
            return self.frozen_at
        return self.base.now() + self.skew


def kill_sensor(ctx):
    """Heartbeat stops: evidence dies mid-flight."""
    return replace(ctx, evidence_valid=False)


def forge_observed_at(ctx, forged_at):
    """Sensor dead but timestamp claims freshness (F7)."""
    return replace(ctx, observed_at=forged_at, evidence_valid=True)


def tenant_confusion(ctx, other_tenant):
    """Renderer serving two tenants mixes up contexts (F9)."""
    return replace(ctx, tenant=other_tenant)


def timeout_after_accept(kernel, tenant, owner, key, facts_v1, facts_v2, now):
    """Upstream times out, then returns revised facts for the same request key.
    Returns (first_accept, second_accept, capsule_facts)."""
    first = kernel.accept(tenant, owner, key, facts_v1, now)
    second = kernel.accept(tenant, owner, key, facts_v2, now + 1)
    return first, second


def incomplete_derive(key, value, declared_deps):
    """Planner declares a subset of the true dependencies (F8)."""
    return Kernel.derive(key, value, declared_deps)
