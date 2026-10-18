# SEAT_VERDICT.md — S5: Privacy SLO Lab (measurement seat)

**Lens:** Measurement. Signature question: *"Can you falsify the privacy claim? If not,
you don't have a claim — you have a slogan."*
**Verdict: CONDITIONAL PASS — the harness is honest and well-built, but the privacy SLO
it exists to serve is currently unmeasurable. A release-blocking SLO with no instrument
is theater.**

## What's strong (keep)

1. **The existing harness is epistemically honest.** It states what a PASS does NOT prove
   (no production security, no timing-channel absence, no real listener detection) and
   ships a negative control. This is the right foundation to extend.
2. **Paired-world grammar is the right test shape.** Worlds differing only in a secret,
   public-trace comparison across STATUS/TEXT/STRUCTURED/COUNT — this is counterfactual
   testing done correctly at the mechanism layer.
3. **stdlib-only, auditable.** A test tool's selling point is that it can be audited.
   The ~60-line HTTP client is the right call.

## What breaks (from the measurement lens)

1. **F1 [Critical]: The privacy SLO has no instrument.** FINAL-ARCHITECTURE.md §9
   declares existence AUC ≈ 0.5 "release-blocking." Nothing in the repo measures it.
   No adversarial listener exists. The SLO is currently a sentence, not a gate.
2. **F2 [Critical]: No Pareto evidence.** The architecture promises a leakage-vs-utility
   Pareto chart against three baselines. The baselines (native, keyword-filter,
   v1-lattice) don't exist as runnable policies. The chart is currently a drawing.
3. **F3 [Major]: Counterfactual grammar is partial.** prenatal→therapy exists (pair 2);
   remove-item, add-guest, replay-yesterday's-alone do not. The last two need a temporal
   + audience dimension the current worlds lack (single owner, single day, no audience).
4. **F4 [Major]: Language-blindness is claimed, unproven.** "Hot path keys on labels,
   never strings" is load-bearing for the global-customization story. No test proves
   disclosure decisions are invariant under string substitution.
5. **F5 [Major]: Layer confusion risk.** The existing harness tests the *server's*
   public-trace invariance (mechanism layer). The headline claims (constant shape →
   AUC≈0.5) live at the *policy* layer. Conflating the two would let a correct server
   certify a leaky policy or vice versa. The lab must test the policy algebra
   explicitly and say so.
6. **F6 [Minor]: Brittle fixture paths.** `tests/test_harness.py` and `fixtureserver.py`
   hardcode `/home/hatch/workspace/earshot-broker-trees/j07/...`. Works today, rots
   tomorrow. Not my lane to rewrite; my new tests will resolve paths robustly.

## What I will build (and what I won't)

- **WILL:** `trace_harness/slo/` — synthetic households (4–6 people, roles, EN/HI/Hinglish
  fixture lexicon, seeded secrets with ground-truth non-audiences, 30 days); 4 baseline
  speaker policies as pure functions; keyword-based adversarial listener (honestly labeled
  as a LOWER BOUND on adversary strength); rank-based existence AUC; secret-inference
  rate vs base rate; owner utility; friction; Pareto runner emitting JSON + SVG + Markdown;
  4 counterfactual suites; negative controls for every new instrument; language-blindness
  test. CLI: `python -m trace_harness slo`.
- **WON'T:** touch `packages/kernel/` (frozen); fork the existing harness (extend it);
  claim the fixture listener bounds a real adversary (it lower-bounds detection: anything
  the keyword listener catches, a stronger one catches too — the other direction is NOT
  claimed); invent server evidence (policy-layer results are labeled as such).

## Kill conditions (mine)

- If the sealed policy's measured existence AUC deviates from 0.5 by > 0.05 → my
  constant-shape implementation is wrong, not the metric. Fix the policy, don't tune
  the test.
- If the v1-lattice policy does NOT leak (AUC < 0.7) → my EXISTENCE tell fixture is too
  weak to discriminate. Strengthen the tell, don't lower the bar.
- If any new instrument's negative control doesn't fire → the instrument is theater.
  Kill it and say so.

## Confidence

75% that the instrument set above, built as specified, makes the privacy SLO falsifiable
without overclaiming. The residual risk is adversary realism (fixture listener) — contained
by the lower-bound labeling, not eliminated.

## Disagree-and-commit

S6 owns final integration and may point this lab at real server traces later. My lab tests
the policy algebra; their wiring tests the deployment. The interface between us is the
`Spoken`/`Episode` dataclass shapes defined in DESIGN.md — frozen once written.
