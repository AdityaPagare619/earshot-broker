"""Fail-closed enforcement of the deployment profile at the release boundary.

The gate lives at the service layer that *calls* the kernel (blueprint §8.2:
Gateway API process), not inside the kernel — the kernel is the frozen,
tested reference; *which profile* is a deployment concern.

Every privileged operation on the release path must pass through
``ProfileGate.check`` before acting. Violations raise ``ProfileViolation``;
they never warn-and-continue. The security event log is content-free:
operation name + profile name + tenant id only. No private data, no secret
topics, no exclusion rules in logs (dossier §12.5).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .profiles import ProfileConfig


class ProfileViolation(Exception):
    """A request attempted an operation its deployment profile forbids."""


# operation -> predicate(profile) is True when the operation is ALLOWED.
_OPERATIONS: dict[str, Callable[[ProfileConfig], bool]] = {
    # Minting a release lease bound to an audience epoch (Pipeline F).
    # Profile A has no controlled renderer, so leases are meaningless there —
    # and dangerous if honored by anything downstream.
    "issue_lease": lambda p: p.allow_lease_issuance,
    # Returning private source values (or unauthorized derivatives) through
    # the room-facing MCP endpoint. Forbidden in both profiles; the flag
    # exists so the invariant is checked, not assumed.
    "reveal_private_via_mcp": lambda p: p.private_reveal_via_mcp,
    # Audience-scoped release segments on a controlled renderer (Profile B).
    "audience_scoped_release": lambda p: (
        p.allow_lease_issuance and p.local_arbiter_required
    ),
    # Personal API access without independent owner authentication.
    "personal_api_unauthenticated": lambda p: False,
    # Durable-public projection + request receipts (Pipeline C/E).
    # Allowed in both profiles: this is the Profile A workhorse.
    "public_projection": lambda p: True,
    # Accepting a private task initiation (sealed task creation).
    "accept_private_task": lambda p: True,
}


@dataclass
class SecurityEvent:
    operation: str
    profile: str
    tenant: str
    allowed: bool


class ProfileGate:
    """Enforces a frozen ProfileConfig. One instance per process."""

    def __init__(self, profile: ProfileConfig,
                 on_event: Optional[Callable[[SecurityEvent], None]] = None):
        self._profile = profile
        self._on_event = on_event or (lambda e: None)

    @property
    def profile(self) -> ProfileConfig:
        return self._profile

    def check(self, operation: str, tenant: str = "unknown") -> None:
        """Permit or raise. Unknown operations are denied (fail closed)."""
        predicate = _OPERATIONS.get(operation)
        allowed = bool(predicate(self._profile)) if predicate else False
        self._on_event(SecurityEvent(
            operation=operation,
            profile=self._profile.name,
            tenant=tenant,
            allowed=allowed,
        ))
        if not allowed:
            raise ProfileViolation(
                f"operation {operation!r} is not permitted under deployment "
                f"profile {self._profile.name!r}"
            )

    def allowed(self, operation: str) -> bool:
        """Non-raising probe for control flow. Still fail-closed on unknown."""
        predicate = _OPERATIONS.get(operation)
        return bool(predicate(self._profile)) if predicate else False
