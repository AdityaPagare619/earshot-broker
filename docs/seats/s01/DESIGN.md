# DESIGN — S1: Quarantine & Slow Lane

**Seat:** S1 · **Home:** `packages/slowlane/` · **Date:** 18 Oct 2026
**Depends on:** frozen contracts (brief §2) · **Touches:** nothing outside
`packages/slowlane/`, `docs/seats/s01/`, `evidence/slowlane/`

## D1 — Frozen dataclasses implemented verbatim (models.py)

`Item`, `SecrecyEdge`, `GeneralizationChain`, `TableRow`, `BeliefState` copied
exactly from the brief. Plus two S1-internal contracts:

- `UnderstandOutput`: `topics: tuple[str,...]`, `entities: dict[str, frozenset[str]]`
  (canonical name → alias set), `sensitive: dict[str, int]` (entity → max depth at
  which it may appear), `sensitivity: float`, `confidence: float`, `lang_detected`.
- `RenderInput`: the *non-secret* fields a renderer may see
  (`kind, time_label, daypart, location_type, counterparty_role`) plus an opaque
  `vault_token` the real backend would resolve inside the slow lane. The fixture
  backend ignores the token — and says so.

**Rejected:** adding convenience methods that mutate (frozen means frozen);
merging `UnderstandOutput` into `Item` (would leak inference state into the
quarantine record — the quarantine record must stay dumb).

## D2 — Quarantine as a state machine, not a flag (quarantine.py)

`ItemState`: `QUARANTINED → COMPILED → RELEASED → EXPIRED`, enforced by
`transition(item, to)`:

- `QUARANTINED → COMPILED` only via `compile()` (verifier passed).
- `COMPILED → RELEASED` via `mark_released()` (broker published the row —
  S2/S3 integration point; S1 provides the hook, not the call).
- Any state → `EXPIRED` via `expire()` (edge `until` passed, superseded, revoked).
- `COMPILED → COMPILED` allowed as *recompile* (new info, e.g. S4's keep_secret
  hot-patch): version increments, never decrements.
- Everything else raises `IllegalTransition`. No silent stays.

**Problem class eliminated:** "the LLM hadn't finished reading it yet" —
unparsed-data leaks are structurally impossible because *uncompiled* is a state,
not a hope.

**Rejected:** timestamps-as-states, soft "quarantine scores" (a continuous
quarantine is a dial; dials get turned).

## D3 — The verifier: four checks, one verdict (verifier.py)

`verify(chain, sensitive, lexicon, history) -> Verdict(passed, failures, checks_run)`.
`sensitive`: `{entity: max_depth}` — entity may appear only at depths ≥ max_depth.
`lexicon`: `{topic: {lang: frozenset(terms)}}` injected as data (fixture EN+HI
shipped; S6's pack replaces it — the verifier never hardcodes a language).

1. **Entity leak check.** Normalize: NFKC → casefold → transliterate (D4) →
   tokenize. For each depth d in {1..4}: no entity with `max_depth > d` may appear
   in `renditions[d]`. Substring match on normalized tokens (catches "Cloudnine"
   inside "Cloudnine Hospital").
2. **Topic lexicon check.** Same normalization; topic terms from the lexicon must
   not appear below the depth where the topic is cleared. Lexicon is per-topic,
   per-language — the check is language-blind, the data is not.
3. **Quasi-identifier check.** Over a bounded `history` of
   `(time_bucket, weekday, location_type)` tuples spoken at revealing depths: if
   the item's tuple would repeat ≥ `threshold` times inside window τ, fail.
   Threshold and τ are explicit data, not magic numbers. (Weakest check — labeled.)
4. **Monotonicity check.** For consecutive depths, the normalized content-token set
   at d must be ⊆ the set at d+1 (stopwords removed). A "generalization" that
   *adds* information is a contradiction — reject.

Two failures → reject. Verdicts are values, not exceptions: the pipeline decides
retry vs fallback.

**Rejected:** regex-only matching (dies on transliteration); LLM-as-verifier
(the verifier is the thing that bounds the LLM — it cannot *be* the LLM);
single-pass fail (one retry, then templates — matches the pipeline spec).

## D4 — Deterministic Devanagari→Latin transliteration (translit.py)

Hand-rolled, stdlib-only, total function over the Devanagari block: independent
vowels, consonants (inherent -a stripped correctly), dependent vowel signs
(matras), anusvara/visarga/nukta, Devanagari digits. ASCII output, lowercase.
Schwa handling: keep it simple and *documented* — inherent-a deletion only at
word-final position and before known matra boundaries would be ideal; v1 deletes
word-final inherent -a only, and the verifier's token matching is tolerant
(substring), so residual schwa noise cannot *hide* a leak, only (rarely)
over-match. Over-matching fails closed. **Fail-closed asymmetry is the design.**

**Rejected:** pulling in `indic-transliteration` (stdlib-only law); skipping
transliteration and claiming "multilingual" (theater).

## D5 — Boring templates + LLM-shaped interface (render.py)

```python
class RenderBackend(abc.ABC):
    def draft_chain(self, render_input: RenderInput) -> DraftChain: ...
```

`TemplateRenderBackend` (the fixture): per-kind boring templates —
event: d2 `"an appointment at {time}"`, d1 `"something this {daypart}"`;
delivery: d2 `"a package arriving {daypart}"`, d1 `"something arriving {daypart}"`;
reminder/note/message_summary analogues. d4/d3 from templates are
*deliberately* non-specific: the fixture never invents specifics it wasn't given.
Every class, docstring, and output is labeled `fixture`.

**Problem class eliminated:** "the renderer hallucinated a detail into d2" — the
fixture cannot hallucinate; the real backend's drafts still cross the verifier.

**Rejected:** making the fixture "smart" (a smart fixture is a liar);
passing raw content into the renderer directly (goes through `RenderInput` —
the seam is explicit for the day a real backend resolves the vault token).

## D6 — Disclosure Table compiler (compiler.py)

`compile(item, understand, edges, role_defaults, chain, version) -> TableRow`:

- `sensitivity = clamp(understand.sensitivity, 0, 1)`; unknown → 1.0 (fail private).
- `clearance[p] = min(edge-imposed depths for p or p's roles, role_defaults[p])`.
  Edges are *inputs* (S4 produces them); the compiler applies, never invents.
- `chain` must be a verifier-passed chain (the compiler asserts
  `verdict.passed`, else raises — defense in depth, not trust).
- `version`: caller-supplied, must be > previous version for the item
  (compiler tracks per-item versions; replays rejected).

**Rejected:** compiler inferring edges (S4's lane); defaulting unknown persons to
a permissive depth (unknown → 0 unless an edge says otherwise).

## D7 — Confirm queue: it can only make you quieter (confirm.py)

`ConfirmQueue` entries: `edge_confirm` (0.3 ≤ conf < 0.6) and `loosen_request`.
- `resolve(entry_id, decision, authenticated)`: loosen decisions with
  `authenticated=False` → **rejected**, not queued. Recorded either way.
- `sweep(now)`: expired entries → resolved as TIGHTEN (fail private), recorded.
- The queue emits *decisions*, never clearances: S4's gate consumes them.

**Rejected:** a queue with no expiry (dead letters are fail-open timers);
voice-originated loosen entries (never created — by architecture, not by check).

## D8 — Seam-1 projection: the falsifiable boundary (seam.py)

`project_for_hotlane(store) -> dict[item_id, RowView]`: COMPILED/RELEASED items →
their `TableRow`; QUARANTINED/EXPIRED → d0 placeholder only
(`{item_id, state, depth: 0}`). **This function is the seam made executable** —
S2 builds against it, and the counterfactual test asserts on its bytes.

## D9 — Fixture understander (understand.py)

`FixtureUnderstander`: deterministic heuristics over the lexicon — topic detection
by normalized term match, entities from a small alias table, sensitivity from the
max topic sensitivity, confidence fixed at 0.6 (labeled: fixtures don't do
confidence). Produces `UnderstandOutput`. S4-grade inference plugs into the same
output contract later.

## Kill conditions (this seat)

- K1: If the transliterated negative control ever passes (क्लाउडनाइन at d2 not
  caught) → the verifier is theater; halt and redesign, do not tune thresholds.
- K2: If the counterfactual projection differs by even one byte → Seam 1 is
  broken; halt.
- K3: If any test requires the fixture to be "smart" to pass → the test is
  wrong; rewrite the test, not the fixture.

## Lane boundaries (disagree-and-commit)

- S4 owns: edge inference, monotone acceptance gate, `room`/`keep_secret` tools.
  I consume `SecrecyEdge`, produce `UnderstandOutput`, and report violations
  R1-style — never fix across the lane.
- S6 owns: pack content (lexicons, role defaults, templates). I take them as
  injected data; my built-ins are labeled fixtures.
- S2 owns: everything downstream of `project_for_hotlane`.

---

*Design written after verdict, before code — per protocol.*
