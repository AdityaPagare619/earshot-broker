# SEAT VERDICT — S1: Quarantine & Slow Lane

**Seat:** S1 · **Lens:** Seam 1 — "nothing uncompiled reaches the hot path."
**Date:** 18 Oct 2026 · **Base:** main @ 3324706 (314 tests green)

## The brutal truth

**The slow lane does not exist.** The repo has a frozen 24-test kernel (broker core),
a real MCP gateway, a simulator, adapters, and a trace harness — but Stage 1
(ingest → understand → render → verify → compile) is vapor. Every claim about
"quarantine," "deterministic verification," and "boring templates" is currently a
promise in a markdown file, not a mechanism in code. If the hot lane were wired to
Stage 1 today, there would be no Stage 1.

This is the highest-risk seam in the architecture, and here is why: **Seam 1 is where
AI meets determinism.** Every other seam is pure enforcement. Seam 1 is where a
model's draft becomes speakable truth — and the only thing standing between a
hallucinated rendition and a spoken leak is the verifier I am about to build. If the
verifier is keyword theater, the whole "dumb-LLM doctrine" collapses.

## What's strong (inherited)

1. **The frozen contracts are exactly right.** `Item` / `SecrecyEdge` /
   `GeneralizationChain` / `TableRow` as frozen dataclasses, with the hot lane
   reading *only* `TableRow`, is the correct trust boundary. I will implement them
   verbatim — no drift.
2. **The seam contract is falsifiable.** "Only versioned TableRows + priors cross;
   raw content never" gives me a counterfactual I can actually run: adversarial
   email 5s before briefing → byte-identical hot-lane projection.
3. **The verifier spec names four real checks** (entity, topic, quasi-identifier,
   monotonicity) instead of one regex. That honesty is what makes the job hard —
   and worth doing.

## What would break (my pre-mortem, written before code)

1. **Transliteration theater.** A verifier that checks "Cloudnine" but not
   "क्लाउडनाइन" is a Hindi-shaped hole in a product whose India story is load-bearing.
   There is no ICU here — stdlib only — so I hand-roll a deterministic
   Devanagari→Latin map and *prove* it with a negative control. If I can't make
   क्लाउडनाइन fail verification at d2, I have built nothing.
2. **Lane collision with S4.** Edge inference + the monotone gate are S4's mandate;
   my compiler needs edges as input. If I invent my own edge semantics, the two
   seats fork the trust model. **Resolution:** I consume the frozen `SecrecyEdge`
   dataclass as an *input* contract, produce `UnderstandOutput` (topics/entities/
   sensitivity) as S4's input, and touch neither inference nor the acceptance gate.
   The boundary is documented in DESIGN.md; violations get reported R1-style, not
   fixed across lanes.
3. **The confirm queue becomes a dead letter.** A queue nobody resolves is a
   fail-open timer. My design: unresolved entries *expire into TIGHTEN*, and
   loosening without `authenticated=True` is rejected, not queued. The queue can
   only make the system quieter.
4. **Fixture creep.** The fixture render backend (templates) must never be mistaken
   for the LLM path. Every fixture artifact is labeled `fixture` in its name,
   docstring, and output. The `RenderBackend` ABC is shaped so a real LLM plugs in
   with zero verifier changes.
5. **Quasi-identifier hand-waving.** "Time + recurrence + location patterns" is easy
   to write and easy to fake. My version: a counting check over (time-bucket,
   weekday, location-type) tuples against a bounded exposure history, with the
   threshold as explicit data. Small, real, labeled as v1 of that check.

## Confidence

70% that the verifier as specified closes the stated leak classes; 40% that the
quasi-identifier check is the right final form (it's the weakest of the four —
flagged honestly, shipped simply). 95% that quarantine + projection counterfactual
holds: that one is structural, not clever.

## What I will not do

- Touch `packages/kernel/`. (Frozen. Ever.)
- Invent edge-inference semantics. (S4's lane.)
- Invent role defaults or lexicon content beyond a labeled fixture. (S6's pack.)
- Claim the fixture renderer is "LLM-equivalent." It is templates. It says so.

---

*Verdict written before design; design written before code — per protocol.*
