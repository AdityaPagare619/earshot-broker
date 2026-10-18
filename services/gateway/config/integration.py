"""Reference wiring: how the Gateway API consults the profile switch.

This module is the integration *pattern* for J3's MCP server — not a server
itself. Its job is to prove the switch changes behavior: the same
``ReleasePath`` methods issue leases under ``controlled_host_demo`` and
refuse under ``public_persistent_host``. J3 should wire the real transport
against ``ProfileGate`` the same way.

Two release paths, mirroring the dossier pipelines:

* ``public_release`` (Pipeline C/E) — the Profile A workhorse. Creates the
  request receipt *before* private lookup, returns only the public
  projection. Allowed in both profiles.
* ``audience_scoped_release`` (Pipeline F) — controlled host only. Requires
  a live sensor heartbeat and a ready local arbiter (injected preconditions;
  J2 owns the real sensor), mints a short lease, and redeems it only if the
  audience epoch, policy version, and evidence are still current at commit.

Heartbeat/arbiter are injected callables so the *mechanism* (check before
issue) is real while the *sensor* stays honestly stubbed at this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .gate import ProfileGate


@dataclass(frozen=True)
class Heartbeat:
    alive: bool
    observed_at: float


@dataclass(frozen=True)
class ArbiterState:
    ready: bool


class StaleEvidence(Exception):
    """Sensor evidence too old to authorize an audience-scoped release."""


class ReleasePath:
    """Profile-aware release path. One instance per gateway process."""

    def __init__(self, gate: ProfileGate, kernel,
                 heartbeat: Callable[[], Heartbeat],
                 arbiter: Callable[[], ArbiterState]):
        self._gate = gate
        self._kernel = kernel
        self._heartbeat = heartbeat
        self._arbiter = arbiter

    @property
    def profile_name(self) -> str:
        return self._gate.profile.name

    def public_release(self, tenant: str, owner: str, request_key: str,
                       facts, now: float) -> dict:
        """Sealed-task intake returning only the public projection.

        Receipt is created before any private lookup (dossier Pipeline C);
        the receipt text is random and created even for empty results.
        """
        self._gate.check("public_projection", tenant=tenant)
        receipt = self._kernel.accept(tenant, owner, request_key, facts, now)
        public = self._kernel.public_projection(facts)
        return {
            "request_ref": receipt["receipt"],
            "state": receipt["state"],
            "public_facts": list(public),
            "public_message": receipt["public_message"],
        }

    def audience_scoped_release(self, tenant: str, fact, ctx,
                                now: float) -> Optional[str]:
        """Mint-and-redeem a short audience-bound lease. Controlled host only.

        Returns the released value, or None when the lease cannot be
        committed (expired, epoch moved, audience changed). Raises
        ProfileViolation under public_persistent_host and StaleEvidence when
        the heartbeat is dead or stale.
        """
        self._gate.check("audience_scoped_release", tenant=tenant)

        hb = self._heartbeat()
        ttl = self._gate.profile.evidence_ttl_seconds
        if not hb.alive or now - hb.observed_at > ttl:
            raise StaleEvidence(
                "sensor heartbeat dead or older than evidence TTL; "
                "audience-scoped release denied")
        if not self._arbiter().ready:
            raise StaleEvidence("local arbiter not ready; release denied")

        lease = self._kernel.prepare(fact, ctx, now)
        if lease is None:
            return None
        return self._kernel.redeem(lease, ctx, now)
