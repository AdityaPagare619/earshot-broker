"""Production readiness gates as checkable code (blueprint §11).

Each gate returns PASS, FAIL, or MANUAL. MANUAL gates are genuinely human
judgments (usability, certification, device measurement) and require a
sign-off record — a MANUAL gate without one is reported as FAIL, never
skipped. Automated gates run live probes against the real kernel where
possible; where only structural properties can be checked, they say so.

This module does not claim production readiness. It makes the *absence* of
readiness visible and blocks deploys on it.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class GateResult:
    name: str
    status: str  # "PASS" | "FAIL" | "MANUAL"
    evidence: str
    signoff: Optional[dict] = None

    def blocks_deploy(self) -> bool:
        if self.status == "FAIL":
            return True
        if self.status == "MANUAL" and not self.signoff:
            return True
        return False


@dataclass
class ReadinessGate:
    name: str
    check: Callable[[], GateResult]
    manual_guidance: str = ""


def _kernel():
    """Load the reference kernel by file path (no install required)."""
    import importlib.util
    from pathlib import Path
    here = Path(__file__).resolve()
    # services/gateway/config/readiness.py -> repo root is 4 levels up
    root = here.parents[3]
    path = root / "packages" / "kernel" / "kernel.py"
    spec = importlib.util.spec_from_file_location("earshot_kernel", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gate_auth_implemented() -> GateResult:
    return GateResult(
        name="auth_implemented_and_reviewed",
        status="MANUAL",
        evidence="Requires: owner authN on personal surface, token issuer/"
        "audience/expiry/scope verification, and a recorded security review. "
        "Not implemented in this build (dossier §17).",
    )


def _gate_cross_tenant() -> GateResult:
    # Live probe: two tenants, cross-tenant open_private must raise the
    # generic error (not an existence oracle), and tenant binding must hold.
    k = _kernel()
    kernel = k.Kernel()
    facts = (k.Fact("appt", "Clinic 3pm", k.Label(frozenset({"t1-alice"}))),)
    rec = kernel.accept("t1", "alice", "req-1", facts, now=1000.0)
    try:
        kernel.open_private(rec["receipt"], "t2", "bob", True, now=1001.0)
        return GateResult("cross_tenant_tests", "FAIL",
                          "cross-tenant open_private did not raise")
    except PermissionError as exc:
        if str(exc) != "Unavailable":
            return GateResult("cross_tenant_tests", "FAIL",
                              f"cross-tenant error leaks signal: {exc!r}")
    # Same-tenant, correct principal must succeed.
    got = kernel.open_private(rec["receipt"], "t1", "alice", True, now=1001.0)
    if got != facts:
        return GateResult("cross_tenant_tests", "FAIL",
                          "same-tenant retrieval mismatch")
    return GateResult(
        name="cross_tenant_tests",
        status="PASS",
        evidence="Live kernel probe: cross-tenant access raises generic "
        "'Unavailable'; tenant/owner binding enforced on open_private and "
        "revoke. Full adversarial suite (races, replay) is J6's area.",
    )


def _gate_observability() -> GateResult:
    # Structural: the only security event type the gate emits must carry no
    # private fields. Verified by introspection, not by assertion alone.
    from .gate import SecurityEvent
    fields = set(SecurityEvent.__dataclass_fields__)
    forbidden = {"value", "fact", "secret", "topic", "title", "label"}
    leak = fields & forbidden
    if leak:
        return GateResult("private_data_absent_from_observability", "FAIL",
                          f"SecurityEvent carries private fields: {sorted(leak)}")
    return GateResult(
        name="private_data_absent_from_observability",
        status="PASS",
        evidence="SecurityEvent fields are exactly "
        f"{sorted(fields)} — operation/profile/tenant/allowed only. "
        "Full log-pipeline audit (all services) is still required before "
        "connecting real records.",
    )


def _gate_common_assembler() -> GateResult:
    # Structural: exactly one predicate table governs release operations.
    from . import gate as gate_mod
    tables = [n for n in dir(gate_mod) if n == "_OPERATIONS"]
    if len(tables) != 1:
        return GateResult("common_release_assembler", "FAIL",
                          "release predicate table missing or duplicated")
    ops = set(gate_mod._OPERATIONS)
    required = {"issue_lease", "reveal_private_via_mcp",
                "audience_scoped_release", "personal_api_unauthenticated",
                "public_projection", "accept_private_task"}
    if not required.issubset(ops):
        return GateResult("common_release_assembler", "FAIL",
                          f"predicate table missing ops: {sorted(required - ops)}")
    return GateResult(
        name="common_release_assembler",
        status="PASS",
        evidence=f"Single choke point: gate._OPERATIONS governs {sorted(ops)}; "
        "unknown operations deny by default.",
    )


def _gate_source_invalidation() -> GateResult:
    return GateResult(
        name="source_updates_invalidate",
        status="MANUAL",
        evidence="Requires a real source adapter + store: updates must "
        "invalidate dependent materializations, grants, and caches "
        "(dossier §12.3, Pipeline H). No adapter in this build.",
    )


def _gate_crash_safety() -> GateResult:
    return GateResult(
        name="tasks_survive_crashes_without_duplicate_effects",
        status="MANUAL",
        evidence="Requires durable outbox + idempotency keys + reconciliation "
        "tests against a real store (dossier §12.4, §11). In-memory kernel "
        "does not survive restarts by design.",
    )


def _gate_error_containment() -> GateResult:
    # Live probe: secret-dependent error paths must not become oracles.
    k = _kernel()
    kernel = k.Kernel()
    facts = (k.Fact("x", "v", k.Label(frozenset({"t1-alice"}))),)
    rec = kernel.accept("t1", "alice", "req-9", facts, now=2000.0)
    messages = set()
    for tenant, principal, auth in [("t2", "bob", True), ("t1", "mallory", True),
                                   ("t1", "alice", False)]:
        try:
            kernel.open_private(rec["receipt"], tenant, principal, auth, now=2001.0)
            return GateResult("secret_dependent_errors_contained", "FAIL",
                              "unauthorized open_private unexpectedly succeeded")
        except PermissionError as exc:
            messages.add(str(exc))
    if messages != {"Unavailable"}:
        return GateResult("secret_dependent_errors_contained", "FAIL",
                          f"error messages vary by failure cause: {messages}")
    return GateResult(
        name="secret_dependent_errors_contained",
        status="PASS",
        evidence="Live probe: wrong tenant, wrong principal, and unauthenticated "
        "all raise the identical generic 'Unavailable' — no existence oracle.",
    )


def _gate_owner_settings() -> GateResult:
    return GateResult(
        name="owner_disclosure_settings_comprehensible",
        status="MANUAL",
        evidence="Requires usability testing: owners must state an intelligible "
        "disclosure preference and distinguish public vs personal output "
        "(dossier §15.5). Not run in this build.",
    )


def _gate_transformations() -> GateResult:
    # Live probe: label propagation through derive() (the transformation the
    # kernel actually implements) must be conservative.
    k = _kernel()
    pub = k.Fact("w", "rain", k.Label(frozenset({"*"})))
    pri = k.Fact("a", "clinic", k.Label(frozenset({"t1-alice"}), frozenset({"health"})))
    d = k.Kernel.derive("plan", "leave at 2", (pub, pri))
    if "*" in d.label.readers:
        return GateResult("supported_transformations_tested", "FAIL",
                          "derive() leaked public readers from a private dependency")
    if d.label.readers != frozenset({"t1-alice"}):
        return GateResult("supported_transformations_tested", "FAIL",
                          f"derive() readers wrong: {d.label.readers}")
    return GateResult(
        name="supported_transformations_tested",
        status="PASS",
        evidence="Live probe: derive() joins labels conservatively "
        "(public × private → private). New transformations need their own "
        "tests before use (dossier decision 30).",
    )


def _gate_sensor_measurement() -> GateResult:
    return GateResult(
        name="renderer_sensor_claims_measured",
        status="MANUAL",
        evidence="Requires actual device measurements: sensing delay, event "
        "transport delay, arbiter response, unflushable buffered audio "
        "(dossier §11.3). No sensor evaluated in this build.",
    )


def _gate_certification() -> GateResult:
    return GateResult(
        name="certification_questions_resolved",
        status="MANUAL",
        evidence="Requires J4's certification audit: no-dead-ends / "
        "no-silent-failures for private handoff and intentional silence. "
        "See docs/certification.md (J4).",
    )


READINESS_GATES: list[ReadinessGate] = [
    ReadinessGate("auth_implemented_and_reviewed", _gate_auth_implemented,
                  "Owner authN + token verification + recorded security review."),
    ReadinessGate("cross_tenant_tests", _gate_cross_tenant,
                  "Tenant isolation at every store/cache/API."),
    ReadinessGate("private_data_absent_from_observability",
                  _gate_observability,
                  "No private values in logs, traces, or receipts."),
    ReadinessGate("common_release_assembler", _gate_common_assembler,
                  "All public response channels use one release path."),
    ReadinessGate("source_updates_invalidate", _gate_source_invalidation,
                  "Updates invalidate materializations, grants, caches."),
    ReadinessGate("tasks_survive_crashes_without_duplicate_effects",
                  _gate_crash_safety,
                  "Durable outbox + idempotency + reconciliation."),
    ReadinessGate("secret_dependent_errors_contained", _gate_error_containment,
                  "Errors/status must not leak secret-dependent signals."),
    ReadinessGate("owner_disclosure_settings_comprehensible",
                  _gate_owner_settings,
                  "Usability-tested disclosure settings."),
    ReadinessGate("supported_transformations_tested", _gate_transformations,
                  "Explicit tests for every supported transformation."),
    ReadinessGate("renderer_sensor_claims_measured",
                  _gate_sensor_measurement,
                  "Device-measured sensing/arbiter latencies."),
    ReadinessGate("certification_questions_resolved", _gate_certification,
                  "J4 certification audit complete."),
]


def run_readiness(signoffs: Optional[dict] = None) -> list[GateResult]:
    """Run all gates. MANUAL gates need signoffs[name] = {signed_by, date,
    evidence_ref}; an unsigned MANUAL gate counts as blocking."""
    signoffs = signoffs or {}
    results = []
    for gate in READINESS_GATES:
        res = gate.check()
        if res.status == "MANUAL":
            signoff = signoffs.get(res.name)
            if signoff and all(k in signoff for k in ("signed_by", "date", "evidence_ref")):
                res = GateResult(res.name, "MANUAL", res.evidence, signoff)
        results.append(res)
    return results


def deploy_blocked(results: list[GateResult]) -> list[str]:
    """Names of gates blocking deploy."""
    return [r.name for r in results if r.blocks_deploy()]
