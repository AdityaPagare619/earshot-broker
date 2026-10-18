# SEAT VERDICT — J6: Director of Engineering (rigor + security)

Scoring lens: **Tech Implementation, Idea.** Signature: "Show me the test. Show me
the adversary. Name the residual risk."

Verdict basis: read EARSHOT_REDESIGN.md (§1–§14), IMPLEMENTATION_BLUEPRINT.md,
API_CONTRACTS.json; read `packages/kernel/kernel.py` + `test_kernel.py`; ran all
24 kernel tests — **24/24 pass** (0.012s, stdlib unittest).

## What is strong (would survive my review)

1. **Deny-by-default label algebra.** `Label.join` intersects readers, unions
   topics; PUBLIC is the universal reader set. The math is right and small enough
   to audit in one sitting (147 lines).
2. **Lease binding is thorough.** `redeem()` checks tenant, principal, epoch,
   policy_version, audience equality, expiry, label — six independent conditions.
   The 24 tests cover invalidation well, including the subtle
   epoch-change-without-audience-change case.
3. **No existence oracle.** `open_private`/`revoke` raise the same generic
   `PermissionError('Unavailable')` for missing, foreign, unauthenticated,
   expired, and revoked capsules. Correct.
4. **Stable public receipt shape.** `accept()` returns identical public shape
   regardless of private payload; receipts are CSPRNG (`secrets.token_urlsafe`,
   ~144 bits). The paired test `test_secret_rename_and_existence_do_not_change_public_projection`
   is exactly the right instinct.
5. **Monotonicity property test** over the finite audience lattice — the single
   best test in the file. More of this, everywhere.
6. **Honest docstring.** "NOT production security software" — the kernel does not
   oversell. My suite exists to make sure nobody forgets it.

## What is weak / would FAIL in my review (concrete failure paths)

**F1. `accept()` is unauthenticated — G2 rests on air, and it is worse than it
looks.** `accept(tenant, owner, request_key, facts, now)` takes all-plaintext
caller-supplied strings. Anyone can mint a capsule for `tenant='house-a',
owner='priya'`. Worse — **verified empirically**: `accept()` is idempotent per
`(tenant, owner, request_key)` and returns the *existing* receipt to any caller,
so an attacker who guesses the request key learns the victim's receipt; then
`open_private(receipt, tenant, owner, authenticated=True)` — the flag is also
caller-supplied — returns the victim's facts. Full capsule read, zero
credentials. The docstring says "Production must authenticate these arguments
outside model control" — that layer does not exist in this repo. A downstream
MCP server (J3) wired directly to this API ships a confused deputy with a
remote-readable hole. **This is the single most dangerous property in the
kernel for a hackathon demo that invites judges to "try breaking it."**
Pinned by `test_accept_idempotency_returns_victim_receipt_to_attacker`.
Confidence the current API is production-safe: **5%**.

**F2. Label provenance is trusted, not verified.**
`room_projection` releases whatever carries the PUB label. A buggy or malicious
adapter labeling clinical records `readers={'*'}` leaks *by design* — the kernel
has no provenance check, no adapter allowlist, no label-audit. The adapter
contract (blueprint §3) exists only on paper. My `_meta`/secret-key test
demonstrates the boundary: labels are a trust root, and the trust root is
currently "whoever called accept()."

**F3. Control-flow taint is convention, not mechanism.**
`derive()` requires explicit dependencies — good. But a planner that branches on
private data (`if private_busy: return 'a' else: return 'b'`) and labels the
result PUB bypasses the entire algebra silently. The blueprint (§4) names this;
the kernel cannot see it. This relies on planner discipline + review, i.e., on
humans. Name it as such.

**F4. Timing and traffic side channels are unaddressed.**
`public_projection` is O(n) in the fact tuple; paired worlds with different
private counts may differ in timing. The dossier admits "the current reference
kernel does not implement constant-time transport." My paired-world suite
*measures* timing distributions and reports them — it does not pretend to fix
them.

**F5. Magic constants with no basis.**
Lease TTL 0.25s, capsule TTL 300s, audience evidence TTL 1.0s. No derivation, no
configurability. Acceptable in a reference kernel; must never harden into a
production default without measurement (J1's latency work should own these).

**F6. Receipt = bearer token; theft model unstated.**
Whoever holds the receipt plus a passing `authenticated=True` opens the
capsule. Receipt handling requirements (never log, never put in URLs, bind to
channel) are not stated anywhere. If any seat logs tool-call arguments, receipts
land in logs and G2 degrades to "whoever reads the logs."

**F7. No denial audit trail.**
Repeated `PermissionError`s are not recorded. Receipt-guessing is infeasible
(144 bits), but tenant/principal enumeration and injection probing are
undetectable. Detection is a production gate (blueprint §11); the hook should
exist.

**F8. Sensor honesty is the root assumption and it's invisible in code.**
`Context.observed_at`, `evidence_valid`, `coverage_assumed` are caller-supplied.
A lying sensor sets `observed_at=now` forever and the kernel happily releases.
The dossier is honest about this (§5.2, "conditional"), but the code path from
"sensor event" to `Context` doesn't exist yet — whoever builds it (J2) inherits
the entire trust root. My stale-replay tests cover the *honest-but-delayed*
sensor; the *dishonest* sensor is out of scope and must stay labeled so.

## What I am building (my mandate)

- `tests/paired_world/` — paired-world invariance harness + tests (§14.3):
  no-event vs event, prenatal vs therapy vs oncology, existence on/off,
  count/order/location variations, error-vs-nomatch; observing text, key sets,
  status, byte length, timing distribution, metadata — not just strings.
- `tests/adversarial/` — §14.4 adversarial suite with named attacker personas:
  Mom alone, "I am Priya" impersonation, prompt-injected event text, stale
  sensor replay, cross-user/cross-tenant reference replay, secret in `_meta`,
  plus cross-tenant negative tests.
- `docs/threat-model.md` — the §5 threat model rendered as an engineering
  document with a **residual risk register** naming F1–F8 and what is NOT covered.
- `evidence/j06-*.json` — machine-readable test reports; every claim traces here.

## Calibration

- Kernel's stated guarantees hold within its stated assumptions: **85%**.
- Current repo state is production-shippable: **5%** (it is explicitly a
  reference; the danger is only if anyone forgets).
- My suite will find at least one behavior the dossier implies but the kernel
  doesn't enforce: **70%** (F1/F2/F3 are already candidates).

*Disagree-and-commit: the sealed-task operating principle is the right
foundation. My verdict is against the current enforcement gaps, not the idea.*
