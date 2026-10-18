"""J1 — deployment profiles as real runtime switches.

Operator-owned configuration for the EARSHOT gateway. Profiles are loaded once
at process start, frozen, and can never be changed by a tool call, request
header, or model output. See DESIGN.md.
"""
from .profiles import ProfileConfig, ProfileError, load_profile, PROFILES
from .gate import ProfileGate, ProfileViolation
from .readiness import GateResult, run_readiness, READINESS_GATES

__all__ = [
    "ProfileConfig", "ProfileError", "load_profile", "PROFILES",
    "ProfileGate", "ProfileViolation",
    "GateResult", "run_readiness", "READINESS_GATES",
]
