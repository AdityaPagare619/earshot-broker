# pro-threat — DESIGN.md

## Method

Asset-centric threat modeling, written for a stranger (Devpost judge, 90 seconds,
Windows laptop, never heard of MCP). Every guarantee is stated narrowly with a
test/evidence pointer; anything not listed as guaranteed is not guaranteed.
The adversary is bounded explicitly — casual overhearing by non-owners in a
shared room — and everything outside that boundary is named as out of scope
rather than silently ignored. Residual risks are named with mechanism,
demonstration, fix shape, and owner. A risk leaves the register only when a
test proves the fix.

## What exists today (and why it must change)

- `docs/threat-model.md` (J6-era): solid engineering, but written for insiders
  ("J6", "dossier §5.3", "seat verdicts"). A judge cannot follow it.
- `docs/residual-risks.md` (J10-era): excellent register, but two statuses are
  **stale** — the sealed-speech wave (S1–S6) and J3's gateway auth wrapper landed
  after it was written.
- No `docs/honesty.md` exists. The README carries an honesty section, but there
  is no single real-vs-simulated ledger or kill-conditions list.

## Verified status changes (checked against code, not reports)

1. **R1 (accept() idempotency / open_private auth) → CLOSED at the gateway layer.**
   `services/gateway/mcp/auth.py` binds (tenant, owner) server-side from the
   `Authorization: Bearer` header; `broker.py` keys idempotency on
   `(tenant, owner, key)` from that binding, and `open_private` is called with
   `authenticated=True` only inside `_capsule_facts` using the bound identity.
   Tool arguments never carry identity. The kernel's raw API is still
   unauthenticated *by design* (in-process library) — the documented rule is now
   "never expose the kernel except through the gateway."
2. **RR-4 (accept serves stale facts on revision) → fail-loud at the gateway.**
   `_check_idem` compares canonical params and raises `INVALID_PARAMS` on
   conflicting request_key reuse instead of silently serving the stale capsule.
   The kernel-level dedupe-key shape question remains open, but the exploitable
   gateway path is closed.
3. **NEW — RR-11 (idempotent replay bypasses belief re-evaluation).** Found during
   this lane's code read: `_check_idem` returns the cached sealed response
   *before* any belief/audience evaluation. A caller replaying a `request_key`
   first used in a permissive audience state receives the permissive response
   even after the audience tightened — strictly more powerful than a fresh call
   (which would be re-planned against current belief). Requires the victim's
   bearer token + knowledge of the key. In the full Profile A deployment the
   render-time arbiter epoch check bounds this; the standalone gateway does not
   re-validate. Named honestly with fix shape (bind audience epoch into the
   idempotency check, or re-plan on hit).

## New risks the sealed-speech wave introduces (naming, not fixing)

- **Pack data boundary:** packs are third-party-authorable YAML; the leak-verifier
  is heuristic (it fired twice during S6 dev — proof it works, not proof it's
  complete). A crafted template is a disclosure primitive.
- **Bearer-token theft → availability attack:** `keep_secret` is tighten-only and
  owner-authenticated at transport; a stolen token lets an attacker tighten
  everything (assistant goes silent). Confidentiality holds; availability doesn't.
- **Voice declarations are unauthenticated by construction** (documented in
  `broker.py`) — asymmetric trust makes them tighten-only, so the residual is
  noise/DoS, never disclosure. The sensitivity-0.7 cap on "I'm alone" is a UX
  cost, honestly stated.
- **Timing side channel persists** (J6 R4 carried forward): constant-shape makes
  *content* invariant; planner latency still varies with corpus size.

## Deliverables

1. `docs/threat-model.md` — rewritten for strangers: adversary, assets, three
   trust boundaries (sealed-task, auth, pack-data), what the architecture defeats
   (test pointers), residual risks, in/out of scope.
2. `docs/honesty.md` — new: real-vs-simulated table, what we don't claim
   (retired claims stay retired), kill conditions.
3. `docs/residual-risks.md` — refreshed: R1/RR-4 status updates, RR-11 added,
   sealed-speech-era notes. J10's register structure kept.

## Risks of this lane (self-criticism)

- Doc claims drifting from code → mitigated by reading `auth.py`, `broker.py`,
  `kernel.py` directly and citing file:line-level behavior, not seat reports.
- Test pointers rotting → every cited test name grepped to confirm existence.
- Overwriting J6/J10's precision with judge-friendly vagueness → keeping the
  narrow guarantee statements and the register format; only the framing changes.
