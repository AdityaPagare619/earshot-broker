# DESIGN.md — S5: Privacy SLO Lab

## 1. Problem

The Sealed-Speech Architecture declares a release-blocking privacy SLO (existence
AUC ≈ 0.5) and promises Pareto evidence against three baselines. Neither is measured
anywhere. This seat builds the instruments.

## 2. Key decisions

**D1 — Policy layer, not server layer.** The lab simulates *speaker policies* as pure
functions over synthetic household episodes. The existing trace-harness tests the
server's wire invariance; the SLO lab tests the disclosure policy algebra. Rationale:
the headline claims (constant shape → AUC≈0.5) are properties of the policy, and a
correct server can serve a leaky policy. The two layers must be falsifiable
independently. The sealed policy mirrors `kernel.public_projection` semantics
(speaks only owner-cleared facts); the bridge to wire traces is S6's integration.

**D2 — Four baselines as pure functions with identical input.**
`native` (says everything), `keyword` (deny-list redaction per language — deliberately
leaky), `v1_lattice` (FULL/ABSTRACT/EXISTENCE/SILENT with the EXISTENCE tell),
`sealed_speech` (constant shape). Same episodes in, `Spoken` out. Any behavioral
difference is policy, not data.

**D3 — Adversary as a lower bound, labeled.** The adversarial listener is
keyword-based, hears only what was spoken in each listener's presence, and performs
two tasks: existence classification (secret-day vs clean-day) and secret-topic
inference vs base rate. It is *explicitly* a lower bound: anything it catches, a
stronger adversary catches too. We never claim the reverse.

**D4 — AUC by Mann-Whitney (stdlib).** No sklearn. `auc = P(score(secret_day) >
score(clean_day))` via ranks, with tie correction. Deterministic, auditable.

**D5 — Seeded everything.** `random.Random(seed)` for households, belief noise, and
episode sampling. No wall-clock, no network. The evidence report records the seed;
re-running reproduces the numbers bit-for-bit.

**D6 — Fixture lexicon, loudly labeled.** EN/HI/Hinglish strings are fixtures, not a
linguistic claim. Every module docstring says FIXTURE. The language-blindness test
(token-substitution invariance) is what carries the architectural claim, not the
lexicon's quality.

**D7 — Counterfactuals as first-class suites.** Four suites, each (world_a, world_b,
property): `content_swap` (prenatal→therapy), `remove_item`, `add_guest`,
`replay_alone`. Comparison dimensions: text, counts, status, metadata, timing-shape
proxy (voice segments + digest-sent flag — labeled proxy; real timing-shape stays at
the wire layer). Each suite runs on all four policies: sealed must pass all; the
suites must *fail* v1/native where they leak (discrimination check).

**D8 — Negative control per instrument.** Mislabel-a-secret-public for the differ
(exists); drop-the-fixed-suffix for the AUC meter (new); weaken-the-tell is NOT a
control (that would test the fixture, not the instrument). A control must break the
*policy under test*, never the instrument.

## 3. Rejected alternatives

- **R1: LLM-as-listener.** Rejected: non-deterministic, un-auditable, and violates the
  seat's own honesty rule (we'd be grading privacy with the thing whose stupidity the
  architecture is designed to bound). The keyword listener is weaker and proud of it.
- **R2: Driving the real MCP server for the Pareto.** Rejected: the server implements
  one policy (sealed). The Pareto needs four policies on identical data — that means
  four servers or a policy simulator. The simulator is honest about its layer (D1).
- **R3: Single "privacy score."** Rejected: leakage and utility are a Pareto frontier,
  not a scalar. Collapsing them hides the trade the judges need to see.
- **R4: Timing measurements in the lab.** Rejected: policy-level simulation has no
  meaningful timing. Timing-shape is asserted as a structural proxy (constant work for
  constant shape) and measured at the wire layer by the existing harness.

## 4. Module layout (new code only; existing harness untouched)

```
trace_harness/slo/
  __init__.py        public API: run_slo_lab(seed, out_dir) -> report dict
  households.py      Person, Secret, Item, Episode, Household; seeded generator
  lexicon.py         FIXTURE multilingual strings + deny-lists (labeled)
  policies.py        native | keyword | v1_lattice | sealed_speech -> Spoken
  listener.py        AdversarialListener (keyword, lower-bound labeled)
  metrics.py         auc_mann_whitney, inference_rate, utility, friction
  pareto.py          run 4 policies -> points + SVG + JSON
  counterfactuals.py 4 suites -> per-policy pass/fail + discrimination checks
tests/test_slo.py    the instrument tests (see §6)
evidence/slo/        slo-report.md, pareto.json/svg, existence-auc.json,
                     counterfactuals.json (generated, committed)
```

## 5. Frozen shapes (interface with S6)

```python
@dataclass(frozen=True)
class Episode:
    day: int; slot: str                 # "morning" | "evening"
    language: str                      # "en" | "hi" | "hi-Latn"
    audience: frozenset                 # person ids, ground truth
    believed_audience: frozenset        # policy's belief (seeded noise)
    items: tuple                       # Item, each with secret: Secret|None

@dataclass(frozen=True)
class Spoken:
    voice_text: str
    phone_text: str                    # "" if nothing sent
    phone_sent: bool                   # always True in cover mode (sealed)
    mode: str                          # "full" | "cover"
    depths: dict                       # {item_id: depth_int} — the decision record
    segments: int                      # voice segments (timing-shape proxy)
```

## 6. Test plan (tests/test_slo.py)

1. `test_sealed_auc_near_half` — measured AUC ∈ [0.45, 0.55] on 4 households × 60 episodes.
2. `test_v1_leaks_existence` — v1 AUC ≥ 0.7 (discrimination: the tell is catchable).
3. `test_native_leaks_everything` — native AUC == 1.0 (sanity: the meter isn't stuck).
4. `test_negative_control_suffix_drop` — sealed variant without the fixed suffix →
   AUC meter FAILS it (AUC > 0.6). A meter that can't fail is theater.
5. `test_language_blindness` — token-substituted strings → identical depths/modes for
   sealed and v1 (decisions key on labels, never strings).
6. `test_counterfactuals_sealed_pass` — all 4 suites PASS on sealed.
7. `test_counterfactuals_discriminate` — v1 fails content_swap/remove_item/add_guest;
   native fails all four (the suites catch real leaks).
8. `test_pareto_ordering` — sealed: lowest leakage; utility(sealed) > utility(keyword);
   friction(sealed) measured and reported (not asserted).
9. `test_secrets_have_non_audiences` — every seeded secret has a non-empty
   non_audience; every non-audience member is a household person (fixture validity).
10. `test_inference_near_base_rate` — sealed secret-topic inference rate within
    base_rate ± 0.1; v1 above base_rate + 0.2.

## 7. Evidence

`evidence/slo/slo-report.md` — the numbers actually measured (seed recorded), the
Pareto table + SVG, per-suite results, and the "what this does NOT prove" block.
Committed to the repo. Numbers are never hand-edited; the report is generated by
`python -m trace_harness slo`.

## 8. What this does NOT prove (will be in the report)

- The fixture listener lower-bounds adversary strength; a smarter adversary could do
  better. We claim detection of *our own* failure modes, not absence of all.
- Policy-layer results are not server evidence. The wire layer is the existing harness.
- Synthetic households are not real households; belief noise is a fixture model.
