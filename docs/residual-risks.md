# Residual risk register

Every break that cannot be fixed at its current layer, with mechanism,
demonstration, why it is unfixable *there*, fix shape, and owner. A risk
leaves this register only when a test proves the fix — never by rewording.

Origin: J10's red-team register (Oct 2026), updated for the sealed-speech
wave: R1 closed at the gateway layer, RR-4 fail-loud, RR-11 found Nov-side
during the professional migration.

## Open risks

## RR-11 — Idempotent replay bypasses belief re-evaluation (new)

**Mechanism:** the gateway's `_check_idem` (`services/gateway/mcp/broker.py`)
returns the cached sealed response *before* any belief or audience evaluation.
Replaying a `request_key` first used in a permissive audience state returns
the permissive response even after the room has tightened — strictly more
powerful than a fresh call, which would be re-planned against current belief.
**Demonstrated:** by code read (pro-threat lane); no test yet — needs one.
**Why unfixable here:** idempotency is a transport-layer promise; belief is a
pipeline-layer state. The two don't share a key.
**Fix shape:** bind the audience/belief epoch into the idempotency slot, or
re-plan on cache hit and serve the re-planned response.
**Scope note:** in the full Profile A deployment the render-time arbiter epoch
check is *designed* to bound the damage (stale segments are denied at playback
when the epoch advanced on audience change); the standalone gateway has no
such check, and the epoch-bump-on-every-belief-change invariant is a
deployment property, not a verified code invariant.
**Suggested owner:** gateway (J3 seat).

## R2 — Label provenance trusted, not verified

**Mechanism:** a PUBLIC-labeled secret is released by design; the pipeline
cannot detect what the adapter got wrong.
**Why unfixable here:** labels are the pipeline's trust root (threat-model §3,
Boundary 1).
**Fix shape:** adapter allowlist + label audit tooling; adapters fail loudly
on unlabeled fields (already implemented — `services/gateway/adapters/`).
**Suggested owner:** adapters seat.

## R3 — Control-flow taint invisible to the pipeline

**Mechanism:** a planner branching on private data and labeling output PUBLIC
bypasses the label algebra.
**Why unfixable here:** the pipeline sees declared dependencies, not the
planner's true inputs.
**Fix shape:** planner-boundary taint tracking + the counterexample generator
at review time. Defense in depth, not a pipeline fix.
**Suggested owner:** whoever owns the planner (cross-seat).

## R4 — Timing side channel

**Mechanism:** constant-shape makes *content* invariant; planner latency still
varies with corpus size. Measured and reported
(`evidence/j06-timing-report.json`); not bounded.
**Why unfixable here:** the pipeline is not constant-time and batching would
cost the latency budget.
**Fix shape:** batching/padding, or declare it an explicit non-goal.
**Suggested owner:** deployment (J1 seat).

## R6 — Receipt = bearer token

**Mechanism:** theft of the dev bearer token plus the token itself = access;
if any deployment logs tool arguments, the guarantee degrades to "whoever
reads the logs."
**Why unfixable here:** receipt handling policy is deployment configuration,
not code.
**Fix shape:** handling policy (no logs, no URLs, channel binding) + log
scrubbing + replacing dev tokens with OAuth 2.1 / PKCE.
**Suggested owner:** all seats; deployment.

## R7 — No denial audit trail

**Mechanism:** probing (tenant/principal enumeration, injection attempts) is
undetectable — denials are silent by design (no oracle), which also means no
telemetry.
**Why unfixable here:** the silence *is* the defense; adding telemetry risks
adding an oracle.
**Fix shape:** security-event hook that logs *counts and classes* without
per-request distinguishability.
**Suggested owner:** gateway (J3 seat).

## R8 — Sensor honesty is the root assumption

**Mechanism:** `observed_at` / evidence freshness are caller-supplied; a lying
sensor defeats everything. A delayed sensor fails safe (stale → UNKNOWN).
**Why unfixable here:** the pipeline sees timestamps, not sensors.
**Fix shape:** authenticated sensor channel (signed heartbeats, sequence
numbers); heartbeat-loss → expire leases. Liveness must be a *signal*, not a
timestamp.
**Suggested owner:** sensor/arbiter integration (J2 seat).

## RR-1 — Redeem-to-playback window

**Mechanism:** `redeem` returns the plaintext value; a renderer that buffers it
can play it after the epoch advanced. The arbiter's per-chunk
`authorize_playback` refuses stale segments, but cannot reach into the
speaker — the check is voluntary.
**Demonstrated:** `test_buffered_value_plays_after_epoch_advance_naive`.
**Why unfixable here:** the kernel has no audio pipeline and no per-chunk
hook; "already emitted sound remains disclosed" is physics, not a bug.
**Fix shape:** controlled audio pipeline with per-chunk epoch checks *in the
renderer process*, small chunks, no prebuffering of future sentences.
**Suggested owner:** simulator/renderer (J2 seat).

## RR-2 — Renderer-controlled clock defeats TTLs

**Mechanism:** `now` is a caller argument everywhere; freezing it defeats the
lease TTL and sensor TTLs simultaneously.
**Demonstrated:** `test_frozen_clock_defeats_lease_expiry`,
`test_frozen_clock_defeats_sensor_ttl`.
**Why unfixable here:** no trusted time source in the pipeline; freshness is
a property of whoever mints the Context.
**Fix shape:** the arbiter mints all Contexts with its own monotonic clock;
the renderer never supplies time.
**Suggested owner:** gateway/server (J3 seat).

## RR-3 — Forged sensor timestamps

**Mechanism:** a forged-fresh timestamp is indistinguishable from a true-fresh
one. TTL measures timestamp age, never sensor liveness.
**Demonstrated:** `test_forged_fresh_timestamp_indistinguishable`,
`test_heartbeat_gap_vs_timestamp_age`.
**Why unfixable here:** same as RR-2 — timestamps, not sensors.
**Fix shape:** signed heartbeats with sequence numbers (see R8).
**Suggested owner:** sensor/arbiter integration (J2 seat).

## RR-6 — Incomplete dependency declarations launder labels

**Mechanism:** `Kernel.derive` trusts the caller's dependency list; omitting a
secret dependency yields a PUBLIC-labeled derivative.
**Demonstrated:** `test_incomplete_derive_launders_label`.
**Why unfixable here:** the kernel cannot observe the planner's true inputs.
**Fix shape:** taint tracking at the planner boundary (R3's fix covers this).
**Suggested owner:** planner owner (cross-seat).

## RR-7 — Empty-audience release

**Mechanism:** valid evidence of an empty room releases secrets into the
renderer. Arguably intended ("nobody listening") — but "nobody is present"
comes from the Context minter (see R8/RR-3).
**Demonstrated:** `test_empty_audience_releases_everything`.
**Why unfixable here:** it is a policy question, not a code bug.
**Fix shape:** explicit, auditable policy choice; or require owner-presence
proof for HIGH-sensitivity facts even in empty rooms.
**Suggested owner:** product/policy.

## RR-9 — No distributed serialization boundary

**Mechanism:** the arbiter is single-process + `threading.Lock`; the blueprint
requires one logical sequencer per room in a distributed deployment.
**Why unfixable here:** no distributed infrastructure in scope.
**Fix shape:** per-room sequencer (single-writer partition or sticky routing);
linearizable epoch increments.
**Suggested owner:** deployment (J1), gateway (J3).

## RR-10 — Renderer memory

**Mechanism:** a renderer that legitimately received a value (empty room, then
an occupant enters) retains it in memory/caches. No test can prove a negative
— documented, not demonstrated.
**Why unfixable here:** requires renderer-process memory discipline outside
any pipeline contract.
**Fix shape:** Profile A (never return revocable secrets to persistent hosts);
Profile B: fresh public context from authorized structured state after audience
changes, never "sanitized" summaries.
**Suggested owner:** simulator (J2), certification (J4).

## Pack-R1 — Pack verifier is heuristic (new)

**Mechanism:** household packs are third-party-authorable YAML; the
leak-verifier is a heuristic scanner. It caught two real leaks during
development (a `{category}` placeholder leaking "therapy"; a Latin-only gift
regex) — proof it works, not proof it's complete.
**Why unfixable here:** template-language expressiveness vs. static analysis
is an open problem, not a bug.
**Fix shape:** verifier + mandatory human review for third-party packs; keep
the verifier's own test suite (packs/tests, 33 tests) green and growing.
**Suggested owner:** packs seat.

## Bearer-R1 — Token theft enables availability attack (new)

**Mechanism:** `keep_secret` is tighten-only and owner-authenticated at the
transport layer. A stolen bearer token lets an attacker tighten *everything* —
the assistant goes silent about the owner's whole life. Confidentiality
holds; availability does not.
**Why unfixable here:** tightening is defined as always-safe; the vulnerability
is the token's power, not the tool.
**Fix shape:** short-lived tokens, per-tool scopes, anomaly alerting on
mass-tighten patterns. (All require replacing the dev auth layer.)
**Suggested owner:** auth/deployment.

## Closed or controlled (kept for the record)

- **R1 (was Critical) — CLOSED at the gateway layer.** The auth wrapper binds
  (tenant, owner) server-side from the `Authorization` header; idempotency is
  keyed by `(tenant, owner, key)` from that binding; `open_private` receives
  `authenticated=True` only inside `_capsule_facts` with the bound identity.
  Tool arguments never carry identity. The kernel's raw API stays
  unauthenticated *by design* (in-process library) — the rule is "never expose
  the kernel except through the gateway."
- **RR-4 (was: accept serves stale facts) — fail-loud at the gateway.**
  Conflicting `request_key` reuse raises `INVALID_PARAMS` instead of silently
  serving the stale capsule. The kernel-level dedupe-key shape question
  (revision component) remains open.
- **RR-5** (no per-lease revocation): withdrawing one pending grant bumps the
  epoch, denying all pending grants — coarse but safe. A per-grant registry is
  future work.
- **RR-8** (UNKNOWN in label readers): label-authoring footgun, documented;
  needs a policy-compile-time linter.
- **C-1** tenant confusion at redeem/open: denied by tests.
- **C-2** receipt oracle: one generic `PermissionError('Unavailable')` for all
  failure modes; timing oracles out of scope, noted.
- **C-3** crash between prepare and commit: no half-committed state; arbiter
  sweeps expired grants.
- **C-4** clock regression (`now < observed_at`): denied.
