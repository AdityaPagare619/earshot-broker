# Certification audit — EARSHOT private task broker

**Author:** J4 (certification lens). **Status:** design audit + executable evidence,
not a certification claim. **Evidence:** `tests/failure_paths/` (37 tests),
`evidence/failure-path-results.txt`, `tests/failure_paths/certification_matrix.json`.

No Alexa certification review has been passed. This document argues how the design
satisfies the certification principles *as written*, names the open question that
only Amazon can settle, and gives J3 the wire contracts the server must implement.

## 1. The requirements under audit

| # | Requirement (certification principle) | Verdict | Evidence |
|---|---|---|---|
| R1 | No dead ends: every user request yields a useful response | SATISFIED, by construction of the deny→recovery matrix | §2, matrix, `test_deny_recovery` |
| R2 | No silent failures: failures are detectable and diagnosable | SATISFIED, split by surface: public-opaque, control-plane-audited | §3, `test_error_oracle`, `test_lease_lifecycle` |
| R3 | Useful failure recovery: the user can act after a failure | SATISFIED: every denial carries a continuation pointer (C3) | §2, C3 contract |
| R4 | Accurate metadata / no deceptive behavior | SATISFIED: withdraw ≠ undo; states are terminal and truthful | §4, `test_withdraw_reconcile` |
| R5 | Honest capability boundaries | SATISFIED: tested boundary-label registry | §5, `test_boundary_labels` |
| R6 | Existence protection under paired worlds | SATISFIED at the facade: public trace invariant across secret changes | §6, `test_paired_worlds` |

## 2. R1/R3 — the deny→recovery matrix (the core argument)

The highest-risk finding of the seat verdict: intentional withholding is
structurally a dead end *unless* every denial maps to a defined public behavior
and recovery path. The matrix (`tests/failure_paths/certification_matrix.json`,
18 rows) is that mapping. Each row: denial cause → public behavior (always the
opaque per-tool shape, always with a `continuation` pointer) → recovery path →
requirement → exercising test.

Key rows a reviewer will probe:

- **Audience-sensitive content withheld (mom enters):** public surface returns
  the accepted-shape with `continuation: personal_inbox`. The task state is
  preserved; the owner finishes privately without re-entering the goal. This is
  the "useful" in useful failure recovery: the *task* continues even when the
  *broadcast* stops.
- **Strict existence protection (no item count, no buzz):** the silence is
  *declared behavior*, chosen by the owner at onboarding for an explicitly
  marked fixture class. The recovery path is the quiet inbox sync the owner was
  told to expect. Silence ≠ failure because the contract was stated upfront and
  the control plane audits the withholding (§3).
- **Stale/disconnected sensor:** audience degrades to UNKNOWN; disclosure does
  not upgrade. The public surface offers the personal continuation; the control
  plane records degraded capability. Fail-closed is itself a recovery path.
- **Withdraw of an in-flight external effect:** public state `reconciling`,
  never `undone`; exact state is private. Cancellation is confirmed, not
  assumed — and never misreported.

Wire contracts C1–C5 (DESIGN.md) bind J3's server: identical denial shapes (C1),
conflicting-key rejection without oracle (C2), mandatory continuation pointer
(C3), reconciling-not-undone (C4), strict-mode push gate (C5).

## 3. R2 — silence vs silent failure

Certification forbids silent *failures*. Strict mode requires public *silence*.
The design distinguishes them on two surfaces:

- **Public surface:** all denials render identically (same keys, same generic
  message, same continuation pointer; `request_ref` echoed when caller-supplied
  so shapes match successes). `test_error_oracle` proves unknown / revoked /
  expired / wrong-tenant / unauthenticated are indistinguishable, and that no
  secret byte appears in any public string.
- **Control plane:** every denial appends exactly one audit event with the real
  cause (`AuditSink` in tests; `audit_events` table in production per blueprint
  §12.3). Post-hoc, "intentionally withheld" and "crashed" are distinguishable —
  which is precisely what "no silent failures" demands.

The kernel's `prepare()` → `None` collapses three causes into one signal. That
shape is load-bearing for the no-oracle property, so the kernel is untouched;
the facade wraps denials with a control-plane reason code that never crosses to
any public surface (DESIGN.md D2/D4).

## 4. R4 — accurate status

- `withdraw_request` on pending work → `canceled`. On in-flight external effects
  → `reconciling`. The word `undone` never appears on the public surface
  (tested). Cancellation and undo are different operations; the copy enforces it.
- `continue_on_personal_device` returns "Delivery request accepted", never
  "delivered" (dossier decision 52). Enqueue ≠ delivery, tested.
- Double-withdraw is stable and idempotent; a canceled request cannot be
  resolved (tested).

## 5. R5 — honest boundaries (tested registry)

`test_boundary_labels.py` holds the `BOUNDARIES` registry: 12 limitations from
dossier §17, each with an exact plain-language label, each asserted free of
overclaim words (`certified`, `guaranteed`, `production-grade`, `real-time`,
`zero-leak`, …). If a limitation is added to the docs without a registry entry,
the suite fails. The registry is the single source J8 must quote in public copy.

## 6. R6 — paired-world invariance

`test_paired_worlds.py`: for a fixed public request, the public response is
byte-identical (modulo the independently-random `request_ref`) across worlds
differing only in protected content — private vs no private event, prenatal vs
therapy title, one vs many private events. Error paths are likewise identical
across worlds. This is guarantee G5 made executable.

Timing is a coarse bound only (10x, `test_timing_parity`): the reference kernel
does not implement constant-time transport (dossier §14.3), and this document
does not pretend otherwise.

## 7. The open question (framed, not settled)

Dossier §15.4 asks for certification guidance on intentional non-disclosure,
silent proactive withholding, and private continuation under the
no-dead-end/no-redirect principles. This audit shows the design *satisfies those
principles as written* — every withholding has a defined recovery, every silence
is declared and audited. Whether Amazon's reviewers *accept* intentional
non-disclosure as a first-class pattern is a product-feedback question for
Amazon, listed in `docs/ask-amazon.md` (J7). This document does not claim the
answer.

## 8. What is NOT claimed

- No certification has been sought or passed.
- No real OAuth, sensor, audio-stop, or phone-delivery integration.
- No statistical timing proof; no production security proof.
- The 24 kernel tests validate modeled properties, not real-world listener
  detection.
