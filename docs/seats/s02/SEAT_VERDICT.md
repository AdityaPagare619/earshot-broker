# SEAT VERDICT — S2: Belief, Planning & Budgets

**Seat:** S2 · **Lens:** Laws 2, 3, 5 — the hot lane's math (belief fusion, credible
sets, minimax planning, exposure budgets) · **Date:** 18 Oct 2026

## Verdict: the hot lane's brain does not exist yet — and that's exactly my seat.

The kernel (frozen, 24/24) owns sealed tasks, labels, and leases. The gateway (J3)
owns transport and auth. The simulator (J2) owns an output arbiter with audience
TTLs. **None of them computes what the room believes, who is credibly present, or
what may be spoken.** The three quantities my seat owns — P(person present),
the credible set, the planned depth — are the entire difference between "fail-closed
by threshold" (v1) and "fail-closed by construction" (sealed-speech). This is the
highest-leverage unbuilt math in the wave. Confidence: 90%.

## What's strong (keep)

1. **The frozen contracts are well-shaped.** `BeliefState{log_odds, timestamp}` is
   the right snapshot type; `TableRow` carrying sensitivity + per-person clearance +
   chain is exactly what a minimax planner needs. ε(s) = 0.5 − 0.45·s is a sound
   continuous fail-closed: at s=0.95, a 7% presence suspicion is enough to include
   someone.
2. **The asymmetric trust table is the critical insight.** Beacons/declarations/hints
   ADD freely; only authenticated acts REMOVE. This is capability attenuation stated
   as arithmetic, and it is what makes "the model may make you more private, never
   less" executable rather than aspirational.
3. **Budgets as error budgets** (L with per-secret τ) is the only honest answer to
   cumulative inference in the corpus. Per-utterance rules cannot see the ninth
   Tuesday; an accumulator can.

## What breaks / what's missing (brutal)

1. **F1 — The `BeliefState` contract carries no provenance.** `{person: logit}` is a
   snapshot; the "alone" 10-minute half-life and "X left" stickiness need signal
   timestamps to decay correctly. If callers keep only the snapshot, decay becomes
   hand-waving. **My design:** fusion is a pure function of (persons, signal log,
   priors, now) — the caller owns the log, the snapshot stays frozen-contract-clean.
   Flagged for S6 integration: the signal log needs a durable home (not my lane).
2. **F2 — Role resolution is unspecified.** `TableRow.clearance` keys on
   `person_or_role`, but no frozen contract maps person → roles. Without it,
   "role:child defaults" (the kid-safe story) has no executable path.
   **My design:** planner takes `roles: {person: frozenset[role]}` as an explicit
   input (S6's pack provides it); unmatched person → clearance 0 (fail closed).
   If S6 doesn't provide it, the planner refuses to guess — it fails closed.
3. **F3 — Budget identity is ambiguous.** The ledger is per (listener, secret) but
   `TableRow` has no `secret_id`. **My design:** secret identity defaults to
   `item_id`; planner accepts an explicit `secret_of` map (S4's secrecy graph will
   own the real mapping). Documented, not hidden.
4. **F4 — τ (budget half-life) is language-adjacent.** "Long for health, short for
   gifts" requires knowing the topic — but the hot path is language-blind.
   **My design:** τ arrives as data (`tau: {secret_id: seconds}`, pack-provided),
   defaulting to a conservative config value when absent. The hot path never
   infers topic from strings.
5. **F5 — "Owner benefits now" needs a definition.** The architecture's
   PHONE-vs-DEFER branch hinges on whether a phone digest reaches the owner now.
   **My design:** `owner ∈ credible set` → PHONE; else DEFER. Simple, auditable,
   stated in DESIGN.md.
6. **F6 — J2's arbiter and my planner both compute "audience."** Overlap risk:
   the arbiter's TTL-based audience and my belief-based credible set could disagree
   (J2 already fixed one such mismatch live). **Boundary:** my planner outputs the
   planned depth + credible set; the arbiter enforces lease/epoch invalidation.
   S6 integration must test them jointly — named here, owned by S6.

## What I will not build (scope discipline)

- No NLP, no string matching, no language detection in the hot path. Person IDs are
  opaque labels. The moment this module reads a word of content, the language-blind
  guarantee is void.
- No sensing. Beacons, Wi-Fi, calendar guests are *signals in*; how they're sensed
  is S1/simulator territory. My module fuses what it's given, honestly.
- No persistence. The signal log, the ledger store, the priors — owned by callers.
  My functions are pure: same inputs → same outputs, always.

## Kill conditions (if these fail, my design is wrong)

1. A property test finds sensitivity ↑ ⇒ credible set shrinks (fail-closed broken).
2. Any unauthenticated signal type is shown to REMOVE someone from a credible set.
3. plan_briefing over 50 items exceeds 15ms compute on this box (hot-lane budget).
4. S6 cannot supply `roles`/`tau` as data → the language-blind claim needs rework,
   not a string-matching fallback.

## Disagree-and-commit

- I disagree with placing `unknown` handling in sensing: the `unknown`
  pseudo-person belongs in the credible-set math (my seat), with its logit supplied
  by the caller. Committed: `unknown_logit` is an explicit planner input.
- I commit to the frozen `BeliefState` contract exactly as written, even though F1
  makes my life harder. The contract is the coordination mechanism.

**Bottom line:** the math this seat owns is the difference between a privacy story
and a privacy mechanism. Build it pure, test the properties, measure the
milliseconds.
