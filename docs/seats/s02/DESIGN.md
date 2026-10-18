# DESIGN — S2: Belief, Planning & Budgets

**Seat:** S2 · **Home:** `packages/hotlane/` · **Date:** 18 Oct 2026
**Laws:** 2 (room is a belief), 3 (worst credible listener), 5 (cumulative disclosure)

## Decision log

### D1 — Fusion is a pure function of (persons, signal log, priors, now).
The frozen `BeliefState` is a snapshot without provenance, so decay (alone half-life,
"X left" stickiness) cannot be computed from the snapshot alone. Instead of mutating
the contract, the caller owns the signal log and `fuse_belief` recomputes from
scratch: `logit(p) = prior(p) + Σ decayed contributions`. Pure, replayable,
testable. Cost: O(signals × persons) — trivial at household scale.
*Rejected:* incremental mutation of log-odds (hides decay bugs, untestable
half-lives); stuffing provenance into the frozen contract (breaks S3's interface).

### D2 — Asymmetric trust is arithmetic, not policy.
Each signal kind maps to a signed, decaying log-odds contribution with a direction
allowance:

| Signal | Adds listeners | Removes listeners |
|---|---|---|
| BEACON_PRESENT | ✓ (strong, slow decay) | — |
| BEACON_ABSENT | — | weak only (−0.5 logit; phones get left in bedrooms) |
| CALENDAR_GUEST | ✓ (bounded by event window) | ✗ never |
| DECLARE_PRESENT ("X is here") | ✓ sticky until X left | — |
| DECLARE_ABSENT ("X left") | — | cancels sticky + small decaying negative |
| ALONE ("I'm alone") | — | ✓ others, exp decay half-life 10 min, **sensitivity < 0.7 only** |
| ALEXA_HINT | ✓ | **NEVER** (tighten-only, enforced by construction) |
| PRIVATE_NOW (authenticated) | — | ✓ everything, 5-min rectangular window (hard override) |

The ALEXA_HINT row is enforced structurally: the hint code path has no negative
branch. There is no flag to mis-set.

### D3 — High-sensitivity items ignore "alone."
For rows with sensitivity ≥ 0.7, the credible set is computed from beliefs fused
*without* ALONE signals (`alone_max_sensitivity = 0.7`, configurable). A kid saying
"I'm alone" cannot unlock a target-linked secret — the math, not a policy check,
guarantees it. Pinned by a dedicated test.

### D4 — Credible set: ε(s) = 0.5 − 0.45·s, `unknown` included.
`C(s) = {p : sigmoid(logit_p) ≥ ε(s)} ∪ ({unknown} if P_unknown ≥ ε(s))`.
The `unknown` pseudo-person's logit is a caller-supplied input (sensing/S1 owns the
*value*; the *math* is mine). Clearance lookup for `unknown` defaults to 0 when the
pack doesn't set it — fail closed.

### D5 — Minimax then budget then decision.
Per item: `d_minimax = min(effective_clearance(p) for p in C)`. Effective clearance
resolves person id → roles → default 0 (fail closed on unknown). Then the exposure
budget steps `d*` down while any `hidden_from` listener would exceed `B(s)`:
`B(s) = 1 − 0.75·s`; weights `w = {4:1.0, 3:0.5, 2:0.2, 1:0.05, 0:0.0}`; iterate
`d* -= 1` until it fits or hits 0. Then:
- `d* ≥ 1` → SPEAK(d*)
- else if owner ∈ C → PHONE (full content to personal channel) + SPEAK(d0)
- else → DEFER + SPEAK(d0)

`cover_mode = (C − {owner}) ≠ ∅`. PHONE-vs-DEFER (F5) is defined, auditable, final.

### D6 — Budget identity defaults to item_id; τ arrives as data.
`secret_of: {item_id: secret_id}` defaults to identity; `hidden_from:
{secret_id: frozenset[person]}` defaults to empty; `tau: {secret_id: seconds}`
defaults to `default_tau` (7 days — conservative). The hot path never infers topic
from strings (F4). If S4/S6 supply richer mappings, they plug in with zero code
change — the parameters are the integration surface.

### D7 — Language-blind by construction, enforced by test.
The module imports no NLP, does no string matching on content, and a test asserts
the planner's outputs are invariant under content-language permutation: swap every
rendition string for another language's and the planned depths/decisions are
bit-identical. Person IDs are opaque labels, never parsed.

### D8 — ExposureLedger is immutable; recording is explicit.
`ledger.record(exposures) -> new_ledger`. `plan_briefing` is pure and does NOT
mutate the ledger — it returns `pending_exposures`; the speaker (S3) commits after
speaking. No footgun: you cannot "plan and forget to speak" into a corrupted
budget. Only SPEAK(d≥1) exposures are recorded (weight > 0); d0 contributes nothing.

### D9 — The 6-tool surface is untouched by this seat.
S2 owns math, not tools. `room`/`keep_secret` (S4) produce *signals* and *edges*;
my module consumes them. Clean seam, no duplication.

## Rejected alternatives

- **R1 — Kalman/particle filter for belief.** Overkill for ≤10 persons and binary-ish
  signals; log-odds fusion is exact for the naive-Bayes structure, auditable in one
  line, and every term is explainable to a judge. Revisit only if signals become
  genuinely continuous (e.g., acoustic ranging).
- **R2 — Continuous disclosure depth.** You cannot speak 0.6 of a sentence (Synthesis
  Step 18). Beliefs are continuous; speech is discrete. The gradient lives in the
  belief layer, never in the mouth.
- **R3 — Budget as formal differential privacy.** Deliberately an *exposure budget*
  in the SRE sense, not ε-DP. Claiming DP would require a neighboring-worlds
  formalism over speech acts we don't have. Honest naming beats borrowed rigor.
- **R4 — Learning τ from data in the hot path.** Tempting, wrong lane. τ is slow-lane
  knowledge (pack data). The hot path reads it; it never fits it.
- **R5 — Putting `roles` resolution inside TableRow.** Would couple the frozen
  contract to the household pack. Kept as an explicit planner input instead.

## API surface (what S3 calls)

```python
from hotlane import plan_briefing, ExposureLedger, initial_ledger, fuse_belief, credible_set

plan, pending = plan_briefing(
    signals=[...], priors={...}, rows=[TableRow...],
    roles={"mom": frozenset({"role:guest"})},
    hidden_from={"itm_7f3a": frozenset({"mom"})},
    ledger=ledger, tau={"itm_7f3a": 14*86400},
    owner="priya", unknown_logit=logit(0.02), now=t0,
)
# plan.items -> tuple[ItemPlan]  (decision, depth, d_minimax, credible, cover_mode)
# plan.belief -> BeliefState     (frozen contract, exactly)
# s3 speaks, then: ledger2 = ledger.record(plan.pending_exposures)
```

Full API + semantics: `packages/hotlane/README.md`.

## Kill conditions

K1. Property test: sensitivity ↑ ⇒ credible set ⊇ (else fail-closed is broken).
K2. Any unauthenticated signal removes someone from a credible set (else Law 6 is broken).
K3. `plan_briefing` over 50 items > 15ms on this box (hot-lane budget).
K4. Language-permutation invariance fails (language-blindness broken).

## Evidence

- `evidence/hotlane/test-run.txt` — full suite output.
- `evidence/hotlane/latency.txt` — plan_briefing over 50 items, measured.
- `evidence/hotlane/counterfactuals.txt` — prenatal→therapy / add-guest / replay-alone
  invariance checks (planner-level; S5 owns the wire-level versions).
