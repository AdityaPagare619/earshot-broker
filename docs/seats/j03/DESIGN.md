# DESIGN.md — J3: MCP server (`services/gateway/mcp/`)

**Owner:** J3 (single-threaded). **Type:** Type-1-adjacent (public wire contract:
tool schemas frozen by `API_CONTRACTS.json`; protocol behavior frozen here).

## Problem

Expose EARSHOT's sealed-task broker as a real MCP server — Streamable HTTP,
spec **2025-11-25** pinned — implementing the 4 contract tools against the real
kernel, with spec-exact protocol compliance, honest dev auth, and measured
end-to-end latency. No SDK may be used (see R1).

## Decisions

**D1. Hand-rolled stdlib Streamable HTTP server.** `http.server.ThreadingHTTPServer`,
zero dependencies. The wire surface we need (initialize/list/call, notifications,
session headers) is small and fully specified in the 2025-11-25 transport doc,
which I read end to end. Responses: `application/json` single object (no SSE
streams needed for request/response tools — simpler and spec-legal).

**D2. Exact 2025-11-25 negotiation and session semantics.**
- `initialize`: client proposes `protocolVersion`; server answers `2025-11-25`
  (its maximum supported). `MCP-Protocol-Version` header on later requests must
  equal the negotiated version, else **400** (spec §Protocol Version Header).
- Server assigns `MCP-Session-Id` (secrets.token_urlsafe, visible-ASCII) on the
  initialize response; all later requests require it, else **400**; unknown or
  expired (>30 min idle) session → **404** (spec §Session Management).
- `GET` → **405**, `DELETE` → **405** (server offers no standalone SSE streams
  and no client session termination — both explicitly permitted by the spec).
- `Origin` header, when present, must match `http://127.0.0.1:*` or
  `http://localhost:*`, else **403** (spec §Security Warning, DNS rebinding).
  Absent Origin (non-browser clients) is allowed. Localhost-only bind.

**D3. Dev bearer-token auth, identity never from arguments.** `Authorization:
Bearer <token>` required on every request (including initialize); missing/invalid
→ HTTP 401. Token → (tenant, owner) resolved server-side from a registry seeded
at startup (two fixture principals: owner + non-owner household member, for
cross-tenant negative tests). Tool arguments carry no identity — per contracts.
**Labeled non-production:** production would follow the Alexa QuickStart OAuth
2.1 + PKCE profile (dossier §10.4); no IdP exists here, and fake OAuth would be
security theater.

**Blocking gate — J6-F1 (R1) closed at this layer.** J6 proved the kernel's
`accept()`/`open_private()` are caller-supplied-identity APIs: anyone guessing a
request key learns the victim's receipt, and `authenticated=True` is just a flag
(`docs/seats/j06/SEAT_VERDICT.md` F1, pinned by
`test_accept_idempotency_returns_victim_receipt_to_attacker`; kernel untouched by
design). This server IS the "authenticate these arguments outside model control"
layer the kernel docstring demands:
- `(tenant, owner)` is bound exclusively from the verified bearer token.
  Tool schemas contain no identity fields at all.
- `authenticated=True` in `open_private` is asserted by this code only after
  token verification — it is not caller-reachable.
- Idempotency is keyed `(tenant, owner, request_key)` with auth-bound owners,
  so a guessed key yields the attacker's own receipt, never the victim's.
- Unknown vs forbidden `request_ref` → byte-identical `-32603 "Unavailable"`.
Pinned by `tests/test_tools.py`: `test_same_key_different_owner_yields_different_receipt`,
`test_member_cannot_use_owner_ref`,
`test_unknown_ref_indistinguishable_from_forbidden`.

**D4. Tools bound to the real kernel.**
- `prepare_day_brief`: validate date (real calendar date) + IANA timezone
  (zoneinfo) + request_key server-side; `kernel.accept()` creates the sealed
  capsule and receipt **before** private lookup; private interval solver runs
  inside the boundary; response = `{request_ref, accepted, public_facts}` where
  `public_facts` comes only from `Kernel.public_projection` (Profile A) — never
  from private values.
- `resolve_day_change`: request_ref must resolve to a capsule owned by the
  caller's (tenant, owner) — else the generic error (no oracle); change schema
  validated including cross-field rules (`window_end > window_start`,
  `duration_minutes` 5–240); draft-only, no external mutation.
- `continue_on_personal_device`: idempotent outbox enqueue keyed
  `(owner, request_key)`; "accepted" means queued, never delivered.
- `withdraw_request`: `kernel.revoke()`; cannot undo emitted effects —
  response says so honestly.
- Idempotency: `(tenant, owner, request_key)` → stored response; same key +
  different params → error (conflicting reuse rejected, per contracts).

**D5. Error taxonomy with zero secret leakage.** JSON-RPC codes: -32700 parse,
-32600 invalid request, -32601 unknown tool, -32602 invalid params (with the
*field name*, never the value), -32603 internal (generic "Internal error").
Unknown vs forbidden `request_ref` → identical `-32603 "Unavailable"`. No
private values in any error string — tested.

**D6. Latency evidence, client-measured.** `tests/test_latency.py` drives 200
sequential `tools/call prepare_day_brief` round trips via `http.client`,
records p50/p95/p99 + method breakdown, asserts p99 < 500ms, writes
`evidence/latency.json` with methodology. Kernel-only timings are not reported.

**D7. Paired-world invariance at the wire.** `tests/test_paired_world.py`:
identical public requests against worlds differing only in protected content
(absent vs present appointment; prenatal vs therapy title); full response bodies
compared with `request_ref` normalized — must be byte-identical under the
strict fixture.

## Rejected alternatives

- **R1. Use the installed MCP Python SDK.** Rejected: it negotiates 2026-07-28
  exclusively (verified: `MODERN_PROTOCOL_VERSIONS == {'2026-07-28'}`). Using it
  would silently violate the pinned spec — the exact trap dossier §10.3 warns
  about. This was the monkey-first check; the SDK failed it.
- **R2. Pin `mcp==1.x` from PyPI.** Rejected: pulls starlette/uvicorn/pydantic/
  httpx; judge-side reproducibility suffers; and its 2025-11-25 fidelity would
  still need the same wire-level verification I'm doing anyway. stdlib is
  smaller, auditable, and dependency-free.
- **R3. Implement OAuth PKCE now.** Rejected: no IdP, no HTTPS, no user
  accounts in competition scope. A mock OAuth flow would look production-grade
  while proving nothing — security theater is worse than honest dev tokens.

## Frozen contracts

- Tool input/output schemas: `packages/contracts/API_CONTRACTS.json` (verbatim).
- Protocol: MCP 2025-11-25 Streamable HTTP as specified in D2.
- Kernel API: `packages/kernel/kernel.py` as-is (no modifications).

### J4 wire contracts C1–C5 — conformance (verified 18 Oct, seat/j04 @ 6fcdd72)

J4's contracts bind this server; I verified each against the real
implementation rather than trusting the summary. Status:

- **C1 — identical public shape for every tool error: SATISFIED.** All tool
  errors are JSON-RPC `{"code", "message"[, "data"]}`; messages are
  field-name-only (`invalid params: 'request_key'`) or the constant
  `Unavailable`. No `hidden_count`, no reason codes, no secret-derived
  strings. Conflicting-key-reuse is keyed `(tenant, owner, key)` — both from
  the verified token — so its distinct message cannot oracle across
  principals. Pinned by `test_errors_carry_no_private_values` and the R1
  triple.
- **C2 — conflicting `request_key` reuse → same shape as any invalid
  request: SATISFIED.** `-32602`, identical JSON-RPC error shape.
  `test_brief_conflicting_key_reuse_rejected`.
- **C3 — denial carries a continuation pointer, never a bare dead end:
  SATISFIED for task denials.** `UNAVAILABLE` (unknown/forbidden ref) now
  carries `data: {"continuation": "personal_inbox"}` — byte-identical for
  both causes, so the no-oracle property holds.
  `test_unavailable_carries_identical_continuation`. Pure validation
  failures (-32602) deliberately carry no inbox pointer: they are client
  bugs, and the field name in the message IS the actionable pointer;
  `test_validation_errors_have_no_continuation_data` pins this.
- **C4 — withdraw on in-flight external effect: SUBSTANCE SATISFIED,
  vocabulary open.** Withdrawing a receipt now marks every queued outbox
  entry for that receipt `withdrawn` (it can never be acted on) and the
  public message reads "reconciling" for the in-flight case vs the plain
  message otherwise; the surface never claims "undone".
  `test_withdraw_after_continue_reconciles_outbox`,
  `test_withdraw_without_inflight_keeps_plain_message`. RESIDUAL: J4's
  contract wants the literal public *state token* `reconciling`, but
  API_CONTRACTS.json pins `request_state` to const `"accepted"` — changing
  the vocabulary unilaterally would break contract validation and collide
  with the merge. Flagged for merge reconciliation (parent + J4): either
  amend the contract enum or accept the message-level rendering.
- **C5 — strict-mode personal delivery: NOT APPLICABLE to this layer.** The
  server never pushes, sounds, or badges; `continue_on_personal_device`
  returns "accepted = queued, never delivered" (dossier §12.4). C5 binds
  J5's personal surface.

### J6-R1 blocking gate — CLOSED (verified, not asserted)

F1: `accept()` idempotency returned the victim's receipt to anyone guessing
`request_key`; `open_private` trusted caller-supplied `authenticated=True`.
Closure, all in this seat's auth layer (kernel untouched):
1. Identity binds ONLY from the verified bearer token — tool schemas
   contain no identity fields (`additionalProperties: false` rejects
   `tenant`/`owner` smuggling; `test_brief_extra_property_rejected`).
2. `authenticated=True` is asserted by server code in `_capsule_facts`,
   never read from arguments.
3. Idempotency is keyed `(tenant, owner, key)` — same key, different owner
   yields different receipts.
Pinned by `test_same_key_different_owner_yields_different_receipt`,
`test_member_cannot_use_owner_ref`,
`test_unknown_ref_indistinguishable_from_forbidden`.

## Failure modes

Bad version header → 400 · missing session → 400 · expired/unknown session →
404 · bad Origin → 403 · oversize body (>1MB) → 413 · unparseable JSON →
-32700 · unknown tool → -32601 · schema violation → -32602 (field names only) ·
unknown/forbidden ref → -32603 "Unavailable" · internal fault → -32603 generic,
redacted log server-side.

## Honest boundaries

Localhost only, no TLS. In-memory sessions/capsules/outbox — restart loses
state (documented; production would use the dossier's relational schema).
Fixture calendar data, labeled. No real Alexa, no certification, no production
auth. `ui://` resource deferred to stretch (core + tests first).

## Pre-mortem (top 3)

1. A judge's MCP client proposes 2026-07-28 and chokes on our 2025-11-25
   answer → mitigation: negotiation test covers version fallback; README states
   the pin and why.
2. `request_ref` entropy/timing leaks existence → mitigation: paired-world wire
   test + constant-shape responses (ref always present, same keys).
3. Auth header forgotten by J2's simulator → mitigation: 401 carries a clear
   non-secret message; integration point flagged in my report.
