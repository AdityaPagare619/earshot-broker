# DESIGN — S6: Household Pack & Integration

## Problem
Prove the architecture's two load-bearing claims with artifacts, not prose:
(1) the Household Pack is **data** — adding Hindi requires zero code changes;
(2) S1→S2→S3→S4 is **one runnable path** — the 5-beat demo computes, not narrates.

## Decisions

### D1 — Packs are inert YAML-subset text, parsed by a dumb parser.
`packs/base|en|hi/*.yaml` + `packs/yaml_subset.py` (~80 lines: mappings,
sequences, scalars, comments; 2-space indent; nothing else) + `packs/schema.py`
(frozen schema validator) + `packs/loader.py` (base + language overlay merge).
**Why:** if packs were Python files, "data not code" would be a costume. Inert
text + dumb parser makes the claim structural: a household edits text, never code.
**Rejected:** JSON (valid but hostile to human lexicon editing); full YAML via a
vendored parser (new dependency surface, and YAML's complexity is exactly what we
don't want near a trust boundary); TOML (stdlib `tomllib` is read-only — fine,
but YAML-subset reads better for lexicons and the mandate said "YAML-ish").

### D2 — Pack schema is frozen and fails loudly.
`schema.py` validates every pack: required sections (manifest, taxonomy, roles,
templates, lexicon, renditions), value domains (clearance depths 0–4 ints,
confidence 0–1, no empty term lists), no unknown top-level keys. Any violation →
`PackError` with file + line + reason. **Never a silent default.** A broken pack
must scream, because a silently-degraded pack is a privacy hole wearing a config
file.

### D3 — Language overlay model: base + lang, merged by the loader.
`packs/base/` holds the language-independent pack (taxonomy, role defaults,
generalization templates with `{placeholders}`). `packs/en/` and `packs/hi/`
hold only what varies by language (lexicon, rendition templates). The loader
merges base + lang into one validated pack object. **Why:** this is the proof
structure — the Hindi pack is ~120 lines of pure data, and the merge is the only
code that knows languages exist.

### D4 — Hot path consumes `(item_id, depth:int, clearance:int)` + rendition lookup.
The integration pipeline's speak stage takes integer depths and looks up strings
from the merged pack. **No `if lang ==` anywhere in the hot path** — enforced by
`test_language_blind.py`, which (a) runs the same beat under en and hi packs and
asserts identical depth decisions with different strings, and (b) asserts the
hot-path modules' source contains no language-conditional branches.

### D5 — Fixtures, not competing implementations.
`integration/ports.py` documents the four stage interfaces against the frozen
dataclasses. `integration/fixtures/{slowlane,hotlane,shape,secrecy}.py` are thin,
deterministic, contract-faithful sketches — every module docstring says FIXTURE.
When S1–S4 land, their modules replace the fixtures behind the same ports.
**I implement the minimum that makes the story run.**

### D6 — The demo runner computes and asserts.
`demo/five_beats.py` drives the pipeline fixtures through the 5 beats of
FINAL-ARCHITECTURE.md §12. Every beat prints honest labels (`[SIMULATOR]`,
`[FIXTURE]`) + computed values (beliefs, credible sets, depths, spoken text,
ledger entries, phone digest). Beat properties are asserted in
`integration/tests/test_demo_beats.py` — beat 4's shape equality is a test.

### D7 — Seam counterfactuals as integration tests.
One per seam I touch: S1 (adversarial email 5s before briefing → identical output),
S2 (prenatal→therapy swap → identical host bytes), S3 (day-with-secret vs
day-without → identical shape). Plus a negative control: a deliberately broken
pack must fail loudly (schema), and a deliberately mislabeled secret must fail
the shape assertion (proving the test can fail).

### D8 — Touch nothing outside my lane.
No changes to `packages/kernel/` (frozen), `services/gateway/mcp/`,
`apps/simulator/`, or any sibling seat's future home. New top-level dirs:
`packs/`, `integration/`, `demo/`. Seat docs at `docs/seats/s06/`.

## Rejected alternatives
- **R1: Python-dict packs.** Rejected — executable config is code; kills D1's claim.
- **R2: Demo against the live MCP server.** Rejected — `room`/`keep_secret` don't
  exist on the server yet (S4's lane); forcing it would mean building S4's tools
  myself. Contract-level demo now, server wiring when S4 lands.
- **R3: Full slow-lane implementation.** Rejected — that's S1's seat. My fixture
  covers quarantine → deterministic-heuristic edges → template renditions, enough
  to prove the path.
- **R4: Skipping the YAML parser for JSON.** Rejected — lexicons are human-edited;
  JSON's quoting/brace tax invites editing errors that become silent misconfig.

## Kill conditions (my own)
- K1: If the Hindi pack requires any code change outside `packs/hi/`, the
  language-blind claim is dead — report, don't patch.
- K2: If any demo beat's key property can't be asserted in code, cut the beat.
- K3: If a fixture needs to know a language to produce correct depths, D4 is
  violated — redesign the fixture, not the claim.

## Interfaces / ports (for sibling seats)
`integration/ports.py`:
- `SlowLanePort.compile(item) -> TableRow` (S1's real module replaces
  `fixtures.slowlane`)
- `HotLanePort.plan(rows, belief) -> Plan` (S2 replaces `fixtures.hotlane`)
- `ShapePort.assemble(plan, pack) -> Response` (S3 replaces `fixtures.shape`)
- `SecrecyPort.infer_edges(item) -> list[SecrecyEdge]` (S4 replaces
  `fixtures.secrecy`)
All ports speak the frozen dataclasses only.
