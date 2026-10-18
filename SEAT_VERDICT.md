# SEAT VERDICT — J4: Sr Solutions Architect, Alexa (certification)

**Lens:** Technical Implementation, Design.
**Signature question:** *"Certification guidelines: which requirement fails?"*
**Confidence:** 80% that the verdict below names the right highest-risk requirement;
70% that the listed gaps are complete for the reference scope.

## The one-line verdict

The design is unusually honest about its boundaries (§17), and its fail-closed
defaults are real, tested code — not slides. But if this went to Alexa certification
review today, **it would fail on "no dead ends" / useful failure recovery**: the
product's core privacy behavior (intentional withholding, and strict mode's
deliberate silence) is structurally indistinguishable from a dead end, and there is
currently **no requirement-by-requirement mapping** from each denial to what the
user sees and what they can do next. That mapping is my build area, and it does not
exist yet.

## What's strong (from my lens)

1. **Fail-closed is code, not copy.** UNKNOWN as a first-class listener, stale
   evidence widening the audience (`effective_audience`), lease bound to
   tenant/principal/epoch/policy-version, generic `PermissionError('Unavailable')`
   with no existence oracle, a receipt created for *every* invocation including
   empty results. The 24 kernel tests actually exercise these.
2. **The §17 "not completed or claimed" list is the strongest certification asset
   in the dossier.** Most hackathon entries inflate; this one writes down what it
   didn't do. Certification reviewers trust teams that bound their claims.
3. **Two deployment profiles are honestly separated** — Profile B's controls are
   never implied to exist in Profile A. That separation is exactly what prevents
   the classic certification failure of demoing on a controlled host and claiming
   production behavior.
4. **Error hygiene in the kernel is good:** no secret bytes in exceptions,
   `derive()` rejects empty dependencies explicitly, `accept()` is idempotent by
   request key (retry-safe by construction).

## What's weak — the failure list

**F1. No denial→recovery mapping (the requirement that fails).**
`prepare()` and `redeem()` return `None` on denial; `room_projection()` returns
an empty tuple; `open_private()` raises a generic error. The *recovery path*
(personal continuation, re-initiation, quiet inbox) exists as a concept in the
dossier but there is no contract stating: for denial cause X, the public surface
MUST say Y and offer Z. Certification's "no dead ends" does not forbid saying
no — it forbids leaving the user with nothing to do next. Every silent
withholding is a dead end until that mapping exists.

**F2. Silence is required AND forbidden.**
Strict existence protection requires public silence (no item count, no buzz —
dossier §4.3). Certification's "no silent failures" forbids silent failure.
The design must prove its silence is *declared behavior with private audit*,
not an unhandled failure. The kernel has **no audit event log** (blueprint §12.3
wants `audit_events`; the kernel has none), so post-hoc you cannot distinguish
"intentionally withheld" from "crashed silently." A reviewer will ask; there is
currently no artifact to show.

**F3. `prepare()` → `None` is a silent-failure smell at the API level.**
Three distinct causes (uncontrolled renderer, audience not permitted, stale
evidence) collapse into one `None`. Nothing in the type forces the caller to
handle it — a caller that forgets the fallback ships a silent drop. The kernel
is shared/frozen, so I will not rewrite it; I will specify the wrapper contract
(deny with a control-plane reason code, still opaque publicly) and test it.

**F4. Identity binding seam is labeled but untested.**
`accept()` takes `tenant`/`owner` as plain arguments with only a comment:
"Production must authenticate these arguments outside model control." Dossier
decision 12 and §10.4 require binding from verified server context, never
arguments. A spoofed owner id at `accept()` time creates a capsule the
confused deputy controls. The kernel cannot fix this alone — but there is no
test pinning what the server layer (J3) MUST enforce. My failure-path suite
will pin that contract.

**F5. Expiry/revoke UX is unspecified.**
Capsule expires after 300s; revoked/expired/unknown/wrong-tenant all raise the
identical 'Unavailable'. Correct on the public surface (no oracle) — but the
*private* surface needs a distinguishable recovery ("session expired,
re-initiate" vs "revoked by your action"). Unspecified today.

**F6. No timing-parity consideration.**
A denial returning in ~0.01ms vs a success path doing real work is a timing
oracle for existence. The dossier's paired-world tests (§14.3) demand
statistical timing testing; nothing exists yet. Coarse stdlib test at minimum.

**F7. Withdraw ≠ undo is unenforced in copy.**
Kernel has `revoke()` but no in-flight external-effect tracking (blueprint §8
`operation_attempts`). Dossier decisions 58–59: never report "undone" for a
sent email / delivered notification; cancellation enters reconciliation. No
artifact pins the user-visible copy contract today.

**F8. Strict-mode push behavior is a certification gate with no gate.**
Dossier §7: if the OS can't guarantee no secret-dependent badge/sound, disable
push for strict fixtures. That's a shippable/not-shippable condition stated as
prose. My docs will state it as a checklist gate.

## What I will build (my area)

- `docs/certification.md` — requirement-by-requirement audit: no dead ends, no
  silent failures, useful failure recovery, accurate metadata, honest boundaries.
  Every denial cause → public behavior → recovery path → test. Explicit
  "not claimed" list.
- `tests/failure_paths/` — executable audit: error-oracle indistinguishability,
  deny→recovery matrix, lease lifecycle (expiry/epoch/stale/disconnect),
  boundary-label registry, withdraw/reconcile semantics, timing-parity coarse
  check. All stdlib, all green, all traceable to `evidence/`.
- `evidence/failure-path-results.txt` — actual run output.

## Residual risks I am NOT covering (flagged, not owned)

- Real OAuth/PKCE, real sensor calibration, real audio-stop latency — J1/J3/J10.
- The full §14.4 adversarial suite — J6.
- Public copy/support burden — J8.
- Whether Amazon *accepts* intentional non-disclosure under certification at all —
  open product-feedback question (§15.4); my docs frame the argument, they don't
  settle it.

## Disagree-and-commit note

I disagree with collapsing all denials to `None`/generic errors *without* a
control-plane reason channel — it trades away diagnosability that certification
reviewers will demand. I commit to the dossier's public-opacity requirement
absolutely: the reason channel stays server-side, never crosses to any public
surface. The tests will enforce both halves.
