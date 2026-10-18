"""Deployment profiles as immutable, operator-owned runtime switches.

Blueprint §10: "These are deployment controls owned by the service/operator,
not tool arguments a model can set."

Two profiles, exactly as the dossier defines them:

* ``public_persistent_host`` (Profile A) — the shippable design. The
  room-facing host receives only durable-public facts plus request receipts.
  Sensitive facts stay private even when the user appears alone. No leases,
  no audience-scoped release, no private reveal over MCP.
* ``controlled_host_demo`` (Profile B) — the controlled-host demonstration.
  Our host owns context assembly and output; audience changes invalidate
  pending leases. Requires an explicit-consent demo harness, a local arbiter,
  and a sensor heartbeat. Never presented as live device integration.

Loading: ``EARSHOT_PROFILE`` env var selects the profile (no default — a
default is a silent choice). Optional ``EARSHOT_CONFIG_FILE`` points at a TOML
file that may tune *operational* parameters only (TTLs, quotas). Capability
flags are profile-defined and cannot be overridden by the file; an unknown
profile name, an unparsable file, or a forbidden override fails startup.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field


class ProfileError(Exception):
    """Raised when the deployment profile cannot be established safely."""


# Operational tunables a TOML file is allowed to set. Capability flags are
# NOT on this list: they are defined by the profile itself.
_TUNABLES = frozenset({
    "lease_ttl_seconds",
    "evidence_ttl_seconds",
    "receipt_ttl_seconds",
    "max_requests_per_minute_per_tenant",
})


@dataclass(frozen=True)
class ProfileConfig:
    """One frozen deployment profile. Immutable after construction."""

    name: str

    # --- capability flags (blueprint §10) ---
    audience_sensitive_content_to_mcp: bool
    private_reveal_via_mcp: bool
    public_result_status: str          # "permission-dependent" | "explicit_consent_and_assumptions"
    personal_api: str                  # "independently_authenticated"
    allow_lease_issuance: bool
    local_arbiter_required: bool
    sensor_heartbeat_required: bool
    fresh_context_after_epoch_change: bool
    autoplay_after_retrust: bool

    # --- operational tunables (operator-set, safe defaults) ---
    lease_ttl_seconds: float = 0.25
    evidence_ttl_seconds: float = 1.0
    receipt_ttl_seconds: float = 300.0
    max_requests_per_minute_per_tenant: int = 60

    def describe(self) -> dict:
        """Content-free description, safe for logs and startup banners."""
        return {
            "profile": self.name,
            "allow_lease_issuance": self.allow_lease_issuance,
            "private_reveal_via_mcp": self.private_reveal_via_mcp,
            "local_arbiter_required": self.local_arbiter_required,
            "sensor_heartbeat_required": self.sensor_heartbeat_required,
        }


def _base_profiles() -> dict[str, ProfileConfig]:
    return {
        "public_persistent_host": ProfileConfig(
            name="public_persistent_host",
            audience_sensitive_content_to_mcp=False,
            private_reveal_via_mcp=False,
            public_result_status="permission-dependent",
            personal_api="independently_authenticated",
            allow_lease_issuance=False,
            local_arbiter_required=False,
            sensor_heartbeat_required=False,
            fresh_context_after_epoch_change=False,
            autoplay_after_retrust=False,
        ),
        "controlled_host_demo": ProfileConfig(
            name="controlled_host_demo",
            audience_sensitive_content_to_mcp=True,   # explicit consent + assumptions only
            private_reveal_via_mcp=False,             # still never raw private over MCP
            public_result_status="explicit_consent_and_assumptions",
            personal_api="independently_authenticated",
            allow_lease_issuance=True,
            local_arbiter_required=True,
            sensor_heartbeat_required=True,
            fresh_context_after_epoch_change=True,
            autoplay_after_retrust=False,             # never auto-resume sensitive speech
        ),
    }


PROFILES = _base_profiles()


def _apply_toml_overrides(base: ProfileConfig, path: str) -> ProfileConfig:
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"cannot load config file {path!r}: {exc}") from exc

    overrides = data.get("tuning", data) if isinstance(data, dict) else {}
    if not isinstance(overrides, dict):
        raise ProfileError(f"config file {path!r}: top level must be a table")

    forbidden = [k for k in overrides if k not in _TUNABLES]
    if forbidden:
        raise ProfileError(
            f"config file {path!r}: not tunable via file: {sorted(forbidden)}. "
            f"Tunable keys: {sorted(_TUNABLES)}. Capability flags are profile-defined."
        )

    values: dict = {}
    for key in _TUNABLES:
        if key in overrides:
            value = overrides[key]
            if not isinstance(value, (int, float)) or value <= 0:
                raise ProfileError(
                    f"config file {path!r}: {key} must be a positive number"
                )
            values[key] = value

    if not values:
        return base
    # dataclasses.replace on a frozen dataclass returns a new frozen instance.
    from dataclasses import replace
    return replace(base, **values)


def load_profile(env: dict | None = None) -> ProfileConfig:
    """Load and freeze the deployment profile. Fails closed on any problem.

    No default profile: ``EARSHOT_PROFILE`` must name a known profile or the
    process refuses to start.
    """
    env = os.environ if env is None else env
    name = (env.get("EARSHOT_PROFILE") or "").strip()
    if not name:
        raise ProfileError(
            "EARSHOT_PROFILE is not set. Refusing to start without an explicit "
            "deployment profile (no silent default). Set it to "
            "'public_persistent_host' or 'controlled_host_demo'."
        )
    base = PROFILES.get(name)
    if base is None:
        raise ProfileError(
            f"unknown deployment profile {name!r}. Known profiles: "
            f"{sorted(PROFILES)}. Refusing to start."
        )
    config_path = (env.get("EARSHOT_CONFIG_FILE") or "").strip()
    if config_path:
        return _apply_toml_overrides(base, config_path)
    return base
