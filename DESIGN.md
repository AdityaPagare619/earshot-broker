# DESIGN.md — J1 build area: `services/gateway/config/`

**Owner:** J1 (single-threaded). **Type:** Type-1-adjacent (deployment trust
boundary — a profile misconfiguration can leak; treated with Type-1 rigor in
review, Type-2 in reversibility: a bad config rolls back by redeploy).
**Dossier anchor:** blueprint §10 (profiles as operator-owned switches), §11
(readiness gates), §13.1 (latency budgets). Kernel: `packages/kernel/kernel.py`
(24 tests green — verified 18 Oct).

## Problem

Blueprint §10 defines two deployment profiles as *operator-owned deployment
controls*, but no mechanism exists. Today the profiles are prose. A model-facing
tool argument, a misconfigured deploy, or an unknown profile string could silently
run Profile B semantics (lease invalidation, audience-scoped release) on a
persistent host — the exact leak the dossier's G1 guarantee forbids. My area makes
the profiles REAL: immutable runtime switches, fail-closed enforcement, readiness
gates as checkable code, measured latency, and a cost model that answers "who
pays."

## Decision 1 — Profiles are immutable, operator-owned runtime config

`services/gateway/config/profiles.py`: a frozen dataclass `ProfileConfig` with
capability flags per blueprint §10; loaded once at process start from
environment (`EARSHOT_PROFILE`) with an optional TOML file override for
non-secret tuning; validated at startup; the resulting object is frozen
(`__setattr__` blocked after construction).

- `public_persistent_host` (Profile A): `audience_sensitive_content_to_mcp=False`,
  `private_reveal_via_mcp=False`, `public_result_status="permission-dependent"`,
  `personal_api="independently_authenticated"`, `allow_lease_issuance=False`,
  `local_arbiter_required=False`.
- `controlled_host_demo` (Profile B): `audience_sensitive_output=
  "explicit_consent_and_assumptions"`, `local_arbiter_required=True`,
  `sensor_heartbeat_required=True`, `fresh_context_after_epoch_change=True`,
  `autoplay_after_retrust=False`, `allow_lease_issuance=True`.

Unknown profile string → process refuses to start (fail closed). No tool, no MCP
call, no request header can change the profile at runtime.

**Rejected alternatives:**
1. *Profile as a tool argument* (`prepare_day_brief(profile=...)`) — REJECTED:
   the dossier explicitly forbids it ("not tool arguments a model can set"); a
   prompt-injected model could escalate itself from Profile A to B semantics.
2. *Database-driven dynamic profiles* — REJECTED: adds a control plane, an admin
   API, and a whole new privilege tier for a competition build; the switching
   need is per-deployment, not per-request. Revisit only with a real multi-tenant
   operator (Type-2 later).
3. *Hardcoded `if PROFILE_A:` branches scattered through server code* —
   REJECTED: ungreppable, untestable as a unit, and every new call site re-risks
   the boundary. One switch object, consulted at decision points.

## Decision 2 — Fail-closed enforcement at the release boundary

`services/gateway/config/gate.py`: `ProfileGate` wraps a `ProfileConfig` and
exposes `check(operation) -> None | raises ProfileViolation`. The release path
(Pipeline E/F) must call `gate.check("issue_lease")` / `gate.check("reveal_
private_via_mcp")` before acting. Violations raise; they never warn-and-continue.
The kernel stays untouched (Chesterton's fence — it's the verified asset); the
gate lives at the service layer that *calls* the kernel, exactly where blueprint
§8.2 puts the Gateway API process.

**Rejected alternatives:**
1. *Warn-and-continue on violation* — REJECTED: normalization of deviance
   (promotion-gates rule 7); a warning nobody reads is permission.
2. *Per-request profile override header* (`X-Earshot-Profile`) — REJECTED:
   privilege-escalation vector; headers are attacker-controlled input.
3. *Enforcement inside the kernel* — REJECTED: the kernel is the frozen,
   tested reference; other seats (J3, J6) build against it. Policy of *which
   profile* is a deployment concern, not a kernel concern.

## Decision 3 — Readiness gates as code, three-state

`services/gateway/config/readiness.py`: blueprint §11's eleven gates as
`ReadinessGate` objects, each with `name`, `check()` returning
`PASS | FAIL | MANUAL`, and an `evidence` pointer. Automatable gates (tenant
isolation hooks present, observability pipeline free of private data — verified
by static scan of log call sites, outbox durability) run in CI. Genuinely human
gates (usability testing of disclosure settings, certification questions
resolved) are `MANUAL` with a required sign-off record schema
(`signed_by`, `date`, `evidence_ref`) — a MANUAL gate without a sign-off file
fails the suite. No gate may be skipped silently.

**Rejected alternatives:**
1. *Markdown checklist only* — REJECTED: not checkable in CI; rots on contact
   with deadlines.
2. *All gates automated* — REJECTED: dishonest. Usability comprehension and
   certification resolution are human judgments; automating them would be
   theater (principal-mindset §11 anti-theater audit).
3. *Gates as J4's failure-path tests* — REJECTED as sole owner: J4 owns
   failure-path *behavior* tests; readiness gates are *deployment* policy. The
   two compose (readiness references J4's test paths) but neither subsumes the
   other. Overlap flagged in my report.

## Decision 4 — Cost model as parameterized code, not a spreadsheet

`services/gateway/config/analysis/cost_model.py`: inputs
(requests/device/day, private-task fraction, model cost/call, storage/user,
infra $/M requests) → $/device/year, with named low/base/high scenarios and a
sensitivity ranking (which input moves the answer most). Every default is a
*stated assumption*, documented in `docs/impact.md` — the module computes, it
does not assert. Base case will show the bounded-AI planner call as the COGS
driver; caching/precompute and planner-call gating are the named levers.

**Rejected alternatives:**
1. *No cost model ("we'll figure it out")* — REJECTED: leaves the seat's
   signature question unanswered; a finance review kills what engineering
   approved.
2. *Single-point estimate* — REJECTED: hides sensitivity; a VP asks "what breaks
   the model" and a point estimate has no answer. Ranges + break-even analysis
   or nothing.
3. *Vendor pricing baked in* — REJECTED: prices move; the model takes prices as
   inputs with dated defaults, so the analysis survives repricing.

## Decision 5 — Latency: measured kernel + labeled assumptions

`services/gateway/config/analysis/latency.py`: measures the kernel's real
operations (`accept`, `open_private`, `public_projection`, `room_projection`,
`prepare`, `redeem`) with `time.perf_counter` over 10k iterations → p50/p95/p99.
Then composes the dossier §13.1 budget table with two columns: MEASURED (kernel)
vs ASSUMED (network, token validation, DB write — stated, not claimed). The
module *refuses* to print a single "total latency" number without the
assumption column beside it.

**Rejected alternatives:**
1. *Kernel-only microbenchmark presented as system latency* — REJECTED: the
   dossier (§14.2) explicitly forbids this; it's the proxy trap
   (principal-mindset §3).
2. *Full distributed load test* — REJECTED for this build: no infra, ₹0 budget,
   no geography. The honest artifact is measured-kernel + labeled-assumption;
   J10's chaos work can extend it.
3. *Repeating §13.1's table as fact* — REJECTED: those are hypotheses; my table
   supersedes the kernel row with measurement and keeps the rest labeled.

## Frozen contracts (my area's public surface)

```python
# profiles.py
@dataclass(frozen=True)
class ProfileConfig:
    name: str  # "public_persistent_host" | "controlled_host_demo"
    audience_sensitive_content_to_mcp: bool
    private_reveal_via_mcp: bool
    public_result_status: str
    personal_api: str
    allow_lease_issuance: bool
    local_arbiter_required: bool
    sensor_heartbeat_required: bool
    fresh_context_after_epoch_change: bool
    autoplay_after_retrust: bool

def load_profile() -> ProfileConfig
    # reads EARSHOT_PROFILE env (+ optional EARSHOT_CONFIG_FILE TOML);
    # unknown name -> ProfileError; returns frozen config.

# gate.py
class ProfileViolation(Exception): ...
class ProfileGate:
    def __init__(self, profile: ProfileConfig): ...
    def check(self, operation: str) -> None  # raises ProfileViolation
    # operations: "issue_lease", "reveal_private_via_mcp",
    #             "audience_scoped_release", "personal_api_unauthenticated"

# readiness.py
@dataclass(frozen=True)
class GateResult: name: str; status: str  # PASS|FAIL|MANUAL
                        evidence: str; signoff: Optional[dict]
def run_readiness(profile: ProfileConfig) -> list[GateResult]
```

## Failure modes

- `EARSHOT_PROFILE` unset/typo → `ProfileError` at startup; process exits
  non-zero. No default profile (a default is a silent choice).
- Config file present but unparseable → startup failure, never partial config.
- `gate.check()` violation at runtime → `ProfileViolation`, request denied,
  security event logged (content-free: operation name + profile, no private data).
- Readiness `FAIL` or unsigned `MANUAL` → CI red; deploy blocked.
- Cost model with missing input → `ValueError`, never a silent default price.

## Honest boundaries

- The gate enforces *profile semantics*; it does not prove tenant isolation —
  that needs J6's adversarial suite against a real store. My config is
  tenant-aware in shape (`tenant` is a first-class field everywhere) but the
  in-memory kernel has one tenant per process.
- Latency numbers are local-loop measured; the 500ms budget needs J3's
  real-server measurement over the network. My table says so explicitly.
- Cost model defaults are stated assumptions (Oct 2026 public pricing
  knowledge), not quotes. Sensitivity analysis is the deliverable, not the
  point estimate.
- No OAuth, no real sensors, no device integration — per dossier §17, not
  attempted here.
