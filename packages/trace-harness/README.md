# trace-harness — public-trace privacy test harness for MCP servers

Tests the property a room-facing host actually depends on: for paired
synthetic worlds that differ **only in a secret**, the *public trace* —
text, structured content, resources, metadata — must not differ in any
secret-dependent way.

## What this is

A standalone, stdlib-only test tool any MCP server builder can adopt. It
speaks Streamable HTTP (MCP 2025-11-25) to a target server, runs the same
initialized request sequence against paired worlds, normalizes independent
randomness, and reports secret-dependent differences by channel
(STATUS / TEXT / STRUCTURED / COUNT).

## What this does NOT prove

- **Not production security.** A PASS is a necessary condition, not a certificate.
- **Not timing-channel absence.** Timing is bucketed and reported as a weak
  signal; systematic skew needs repeated runs and statistics this tool does
  not claim to be.
- **Not real listener detection.** Worlds are synthetic; sensors are out of scope.
- The bundled fixture server is a test double for the harness's own tests —
  it is not the product server and not a reference implementation.

## Quickstart

```bash
# 1. Self-check: does the harness itself work? (in-process kernel, NOT server evidence)
python -m trace_harness run --selftest --out evidence/

# 2. Full run: harness starts its fixture MCP server and tests it over HTTP
python -m trace_harness run --out evidence/
# -> evidence/trace-harness-report.md + .json
# -> pairs: 5/5 PASS; adversarial: 2/2 PASS

# 3. Unit tests (harness + fixture server + negative control)
python tests/test_harness.py

# 4. SLO lab: privacy as a measurable SLO (adversarial listener,
#    existence-AUC, Pareto over 4 baselines, counterfactual suites)
PYTHONPATH=. python -m trace_harness slo --out evidence/slo --seed 7
python -m unittest discover -s tests -p "test_slo.py"
```

## The SLO lab (`trace_harness/slo/`)

The paired-world harness tests the *server's* wire invariance. The SLO lab tests
the *disclosure policy algebra* — the layer the architecture's headline claims
live on ("the room can't learn what it can't tell apart"). A correct server can
serve a leaky policy; the two layers must be falsifiable independently.

- **Synthetic households**: 4–6 people with roles, 30 days × 2 episodes,
  EN/HI/Hinglish fixture strings, seeded secrets with ground-truth
  non-audiences. Secret days, public items, audiences, and belief noise are
  seeded independently — determinism is total (`seed` reproduces bit-for-bit).
- **Four baseline policies** as pure functions over identical episodes:
  `native` (says everything), `keyword` (deny-list redaction — deliberately
  leaky), `v1_lattice` (FULL/ABSTRACT/EXISTENCE/SILENT with the EXISTENCE
  tell), `sealed_speech` (constant shape: fixed suffix always appended in
  cover mode, phone digest always sent silently, no counts).
- **Adversarial listener**: keyword-based, fixture vocabulary, hears ONLY what
  was spoken in each listener's presence. Explicitly a **lower bound** on
  adversary strength — anything it catches, a stronger adversary catches too.
  Two tasks: existence classification (secret-day vs clean-day) and secret-topic
  inference vs base rate.
- **Existence AUC** (Mann-Whitney, stdlib): sealed 0.497 · v1 0.875 ·
  keyword 0.921 · native 0.928 (seed 7, 200 triples each).
- **Pareto** (leakage vs owner utility) emitted as JSON + SVG + Markdown.
- **Counterfactual suites**: content_swap (prenatal→therapy), remove_item,
  add_guest, replay_alone — public-view invariance (text, segments, phone_sent,
  mode). sealed passes 4/4; v1 and keyword pass only content_swap (the tell is
  content-independent but leaks existence); native fails all four.
- **Negative controls**: a deliberately broken seal (withholding removed) is
  caught by the AUC meter (AUC >> 0.5); the language-blindness test proves
  disclosure decisions are invariant under string token-substitution.
- **Belief model** (fixture): conservative presence estimation — detections may
  add phantoms, never miss. Uncertainty widens the credible set (unknown
  pseudo-person, clearance 0); the measured cost is cover-mode friction when
  actually alone (sealed: 0.060), not silent leaks.

See `evidence/slo/slo-report.md` (generated, committed) for the measured numbers.

## Pointing it at your server

The harness is a library, not just a CLI:

```python
from trace_harness import builtin_pairs, MCPHttpAdapter, run_sequence, \
    normalize_trace, diff_traces

# 1. Load the five world pairs' facts into YOUR server under their tenant
#    names (see trace_harness/worlds.py for the fixture definitions).
# 2. Drive it:
for pair in builtin_pairs():
    a = run_sequence(MCPHttpAdapter(url, pair.world_a.tenant, pair.world_a.owner),
                     pair.world_a)
    b = run_sequence(MCPHttpAdapter(url, pair.world_b.tenant, pair.world_b.owner),
                     pair.world_b)
    verdict = diff_traces(normalize_trace(a), normalize_trace(b))
    print(pair.name, verdict.summary())
```

Your server must implement the four proposed tools
(`prepare_day_brief`, `resolve_day_change`, `continue_on_personal_device`,
`withdraw_request`) with the shapes in `packages/contracts/API_CONTRACTS.json`,
and deny unknown/forged references with a uniform generic error (no existence
oracle). The `adversarial_suite` helper covers reference replay and
double-withdraw.

## The five world pairs

| Pair | Secret difference | Must hold |
|---|---|---|
| `no_private_vs_one_private` | B has one private health fact | identical public trace |
| `prenatal_vs_therapy` | secret *content* differs, shape identical | content indistinguishable |
| `reordered_private_records` | same secrets, different order | order-independent |
| `source_error_vs_no_match` | private sync error vs nothing | error never surfaces |
| `one_vs_several_private` | 1 vs 3 private facts | count not revealed |

Plus adversarial fixtures: cross-tenant reference replay and double
withdraw must produce byte-identical generic denials.

## Design notes

- **Normalize, don't byte-compare.** Receipts and session IDs are *supposed*
  to be independent random values (§14.3). The harness replaces them with
  stable tokens — then separately asserts the raw values actually differed
  (an implementation echoing constants would be a finding, not a pass).
- **The negative control is the point.** `test_negative_control_leak_is_detected`
  mislabels a secret as public and asserts the harness FAILs. A privacy test
  that can't fail is theater.
- **stdlib only.** The Streamable HTTP client is ~60 lines of `http.client` —
  small enough to audit, which is the selling point for a *test tool*.

## Layout

```
trace_harness/
  worlds.py       paired synthetic world fixtures
  adapters.py     MCPHttpAdapter (Streamable HTTP) + KernelDirectAdapter (self-test)
  capture.py      run a script, record TraceSteps
  normalize.py    randomness normalization + independence assertion
  differ.py       difference taxonomy + verdict
  adversarial.py  reference-replay / cross-tenant fixtures
  __main__.py     CLI: run + evidence report
tests/
  fixtureserver.py  test-double MCP server against the real kernel (NOT product)
  test_harness.py   6 tests incl. negative control
```
