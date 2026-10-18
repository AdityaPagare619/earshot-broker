# DESIGN.md — J4: certification failure-path tests + docs

**Owner:** J4 (single-threaded). **Type:** Type-2 (reversible: tests + docs; kernel
untouched). **Scope:** `docs/certification.md`, `tests/failure_paths/`,
`evidence/failure-path-results.txt`. J3 owns server code — I build against the
frozen kernel + contracts + mocks, never waiting.

## Problem

Certification's "no dead ends / no silent failures / useful failure recovery"
requirements are the highest-risk item for EARSHOT (SEAT_VERDICT.md F1–F8), because
the product's core behavior — intentional withholding, strict-mode silence — is
structurally a dead end until every denial maps to a defined public behavior and
recovery path. Nothing executable pins that mapping today.

## Decisions

**D1. Tests are the audit, docs are the argument.**
`docs/certification.md` makes the requirement-by-requirement case; every claim in
it points at a test in `tests/failure_paths/`. A doc claim without a test is
deleted. (Governance: writing is the thinking; tests are the receipt.)

**D2. Never modify the kernel.**
`packages/kernel/kernel.py` is shared and frozen. All failure-path behavior is
tested *against* it; where the kernel's surface is insufficient (F3: `None`
denials), I specify a wrapper contract (`CertifiedDenial`: control-plane reason
code, public-opaque rendering) in docs + test the wrapper, not a kernel rewrite.
Chesterton's fence: the `None`/generic-error shape is load-bearing for the
no-oracle property — I extend around it, not through it.

**D3. Deny→recovery matrix is the central artifact.**
A machine-readable `certification_matrix.json`: each row =
`{denial_cause, public_behavior, recovery_path, requirement, test_id}`.
Tests assert every row; docs narrate it. J2/J8 can consume the JSON for
simulator copy and store listing.

**D4. Public opacity is absolute; control-plane diagnosability is required.**
Tests assert BOTH halves: public surfaces never distinguish denial causes
(no oracle — same error, same shape, same timing class), AND the control plane
records a reasoned audit event per denial (in-memory audit sink in tests;
blueprint `audit_events` table in production). F2's "silence vs silent failure"
distinction lives here.

**D5. Stdlib only, unittest like the kernel.**
No pytest, no hypothesis. Seeded randomness for paired-world shape tests.
Timing-parity is a coarse bound (denial vs success within 10x, not a
statistical proof — labeled as such; the dossier's §14.3 statistical timing
work is beyond this seat's scope and is labeled, not faked).

**D6. Boundary labels are a tested registry, not prose.**
`BOUNDARIES` dict in the test package: each honest boundary from dossier §17
("no device integration", "simulated presence", "no real OAuth", …) is a key
with the exact user-facing label string. Tests assert the registry is complete
against a checklist and that labels contain no overclaim words
("certified", "guaranteed", "production", "real-time").

## Frozen contracts (what J3's server layer MUST satisfy — pinned by my tests)

- C1. Every tool error response has identical public shape regardless of cause
  (no `hidden_count`, no reason codes, no secret-derived strings).
- C2. `prepare_day_brief` with conflicting `request_key` reuse → reject with the
  same shape as any other invalid request (dedupe must not oracle).
- C3. Denial at the MCP layer MUST include a continuation pointer or an explicit
  "check your personal inbox" affordance — never a bare empty result. (The
  "no dead ends" wire contract.)
- C4. `withdraw_request` on an in-flight external effect → public state
  `reconciling`, never `undone`; exact state is private.
- C5. Strict-mode personal delivery: no secret-dependent sound/badge unless the
  OS behavior is verified; else push disabled (gate, not preference).

## Rejected alternatives

1. **Rewrite the kernel to return typed denials.** Rejected: the kernel is the
   shared reference; its `None`/generic-error shape carries the no-oracle
   property that 24 tests verify. A rewrite would void that evidence and
   collide with J3/J6/J10. Wrapper + contract instead.
2. **Docs-only certification argument.** Rejected: a certification doc without
   executable tests is exactly the kind of claim the dossier's §17 honesty
   section warns against. Every requirement gets a test or gets cut.
3. **Statistical timing-proof (constant-time transport).** Rejected: the
   reference kernel explicitly does not implement constant-time transport
   (§14.3); claiming a proof would be dishonest. Coarse parity bound + labeled
   limitation instead.
4. **Testing J3's server before it exists.** Rejected (as blocking): I test
   against the kernel + a mock MCP facade implementing C1–C5, so my suite runs
   green today and becomes an integration gate for J3's server tomorrow.

## Failure modes of this work

- The matrix rots: a new denial cause appears without a row. Guard: a test
  enumerates kernel denial sites (grep for `return None` / `raise`) and asserts
  each is covered by a matrix row.
- Tests pass but the copy lies: J8's store listing promises what the matrix
  doesn't. Guard: matrix JSON is the single source J8 must quote; noted in
  docs.
- Timing bound is flaky on loaded machines. Guard: generous 10x bound, seeded,
  documented as coarse.

## Kill condition

If the kernel's denial surface changes under me (J3/J10 modify kernel.py) such
that >2 tests need semantic (not mechanical) rewrites, I stop and re-scope
with Petu rather than chase a moving target. Hitting this is a successful
outcome, not a failure.

## Pre-mortem (top 3)

1. A reviewer finds a denial path my matrix missed (e.g., a new tool's error
   branch) → mitigation: the denial-site enumeration test.
2. My "no oracle" tests pass but a real timing side-channel exists in J3's
   server → mitigation: label timing work as coarse; C1 covers shape, not
   full side-channel proof.
3. The docs argue certification acceptance that Amazon hasn't granted →
   mitigation: docs frame it as "how we satisfy the requirement as written,"
   with §15.4's open question stated explicitly, never as "certified."
