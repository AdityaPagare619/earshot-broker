# DESIGN.md — J8: public surface (README + support docs + creative-line argument)

Owner: J8 (single-threaded). Type: Type-2 (reversible docs; copy can be
rewritten without breaking anything) — but treated with Type-1 care because
public claims are hard to retract once judged.

## Problem

The repo's public surface must read like a top-tier Appstore listing: a judge
skimming for 30 seconds must land *what it is, why it matters, why it's not
obvious, and why it's trustworthy* — with every claim one hop from evidence.
Currently it reads as a research repo. The gap is presentation, not substance.

## Decisions

1. **README structure: headline → human moment → creative-line → mechanism →
   boundaries-as-trust → evidence → layout → run.** (Amazon Working Backwards:
   the press release before the spec. The dossier's §15.5 pitch and the
   one-liner are the headline; the Priya walk-in is the human moment; §16
   decisions 5–10 become the boundaries section.)
2. **The obvious-vs-creative argument lives in the README, not a side doc.**
   A judge skimming will not open a second file. One tight section,
   explicitly mapped to the rules' "basic MCP wrapper" language, naming what
   we do that a wrapper cannot: sealed tasks, counterfactual privacy, lease
   invalidation on audience change, deterministic boundary with AI inside it.
3. **`docs/support.md` as the support-burden answer.** FAQ (8 skeptical
   questions), troubleshooting table (symptom → cause → fix), known
   limitations, contact path. Every troubleshooting row must reference a real
   behavior or be marked planned — no invented failure modes.
4. **Boundaries framed as trust, not apology.** "What we don't claim" section
   positioned as the reason the claimed parts are believable (dossier §2.2–2.3
   corrections are the source material).
5. **Every number gets an inline evidence link.** "24 tests" → 
   `evidence/kernel-tests.txt`; scenario trace → 
   `evidence/synthetic-scenario-trace.json`; handshake → `evidence/*.json`.
   One hop, no hunting.
6. **No new claims invented.** I write copy only from the dossier, evidence/,
   and contracts. If a sentence needs a fact I don't have, the sentence dies.

## Alternatives considered and REJECTED

1. **Marketing-style superlatives ("revolutionary", "first-ever", "best").**
   REJECTED: the dossier explicitly forbids uncheckable claims (§15.5: gallery
   unpublished — do not claim "no competitor does this"). Superlatives are
   what Appstore review rejects; our moat is checkable honesty. Every
   adjective I use must survive a hostile reading.
2. **Separate `docs/why-not-obvious.md` page for the creative-line argument.**
   REJECTED: judges skim; a second file won't be opened in the critical
   30 seconds. The argument must live in the README's first screen. (A
   longer-form version may exist later; the README carries the case.)
3. **FAQ that invents answers for unbuilt behavior.** REJECTED: J4/J6 own
   failure paths and adversarial behavior. My FAQ answers only what the
   dossier + kernel + evidence establish; anything else is marked "not yet
   characterized — see open questions" with a pointer. Invented support
   answers are worse than missing ones (support-burden lens: wrong docs
   create tickets).
4. **Hiding the simulator label to look more "real."** REJECTED: dossier §16
   decision 6 ("label the controlled host as a simulator") and §2.1 (gated
   tooling → independent simulator is the honest path). The listing states
   "controlled-host demo, not an Echo" prominently. Trust compounds.

## Frozen contracts (inputs I build against)

- Dossier `EARSHOT_REDESIGN.md` + `IMPLEMENTATION_BLUEPRINT.md` — claim source.
- `packages/contracts/API_CONTRACTS.json` — the 4 tool names/descriptions.
- `evidence/VALIDATION_SUMMARY.md` — what was actually checked; my copy's
  ceiling.
- J2 owns simulator mechanics; J7 owns ask-amazon. I link, never duplicate.

## Failure modes

- **Copy overclaims** (my #1 risk): an adjective implies device integration
  or production security. Mitigation: re-read every claim against
  evidence/VALIDATION_SUMMARY.md "Limits" before commit; grep for banned
  words (universal, guaranteed, proven, first, all Alexa).
- **Stale copy**: another seat ships a behavior my docs describe differently.
  Mitigation: my docs describe only dossier-level contracts (stable), not
  seat implementations (moving); integration points flagged in my report.
- **FAQ answers a question the build can't**: mitigation per decision 3 —
  mark unknowns honestly.

## Honest boundaries (this seat)

- I do not write about simulator UX mechanics (J2), certification posture
  (J4), threat model internals (J6), or the Amazon ask (J7) beyond one-line
  pointers.
- No performance numbers beyond what evidence/ establishes (kernel unit
  timing only; no network/latency claims — dossier §17 says none measured).
- The README will state the demo uses synthetic data (dossier §16.3).

## Done when

README reads top-to-bottom as a listing; support.md answers the 8 questions;
every number has a one-hop evidence link; a hostile read finds no
overclaim; branch pushed.
