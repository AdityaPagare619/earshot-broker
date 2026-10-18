# packages/hotlane — Belief, Planning & Budgets (S2)

Pure functions implementing Laws 2, 3, 5 of the Sealed-Speech Architecture.
Stdlib only. No I/O. No NLP. No sensing. The hot path operates on
`(item_id, depth:int, clearance:int)` — integers and labels, never strings.

## The one call S3 needs

```python
from hotlane import plan_briefing, initial_ledger

plan = plan_briefing(
    signals=[...],          # Signal log (caller-owned): beacons, declares, hints...
    priors={"priya": 2.2},  # logit P(present) per person — rhythm priors / pack
    rows=[TableRow...],     # the ONLY thing the hot lane reads (frozen contract)
    owner="priya",
    ledger=initial_ledger(),
    roles={"maya": frozenset({"role:child"})},      # pack-provided (S6)
    hidden_from={"itm_7f3a": frozenset({"mom"})},   # S4's secrecy graph, flattened
    secret_of={"a": "secretS"},                     # default: item_id IS the secret
    tau={"secretS": 14 * 86400},                    # per-secret budget half-life (pack data)
    unknown_logit=-3.9,                             # P(unmodeled visitor); sensing owns the value
    now=time.time(),
)
for item_plan in plan.items:
    # item_plan.decision: "speak" | "phone" | "defer"
    # item_plan.depth:    speak depth (0 for phone/defer — absorbed)
    # item_plan.cover_mode, .credible, .d_minimax, .sensitivity
    ...
# AFTER speaking:
ledger2 = ledger.record(plan.pending_exposures)
```

`plan_briefing` is pure: it never mutates the ledger. Commit exposures after
speaking. `plan.belief` is the frozen `BeliefState` snapshot.

## Module map

| Module | Owns |
|---|---|
| `contracts.py` | Frozen dataclasses, verbatim from the brief (Item, SecrecyEdge, GeneralizationChain, TableRow, BeliefState) |
| `belief.py` | `Signal`, `fuse_belief` — log-odds fusion with the asymmetric trust table |
| `credible.py` | `epsilon(s) = 0.5 − 0.45·s`, `credible_set` — includes the `unknown` pseudo-person |
| `chain.py` | Depth constants, `LEAKAGE_WEIGHT`, `validate_chain`, `render` (table lookup) |
| `budgets.py` | `Exposure`, immutable `ExposureLedger`, `L(p,s,t)` with per-secret τ |
| `planner.py` | `plan_item`, `plan_briefing`, minimax + budget cap + SPEAK/PHONE/DEFER |

## The asymmetric trust table

| Signal | Adds | Removes |
|---|---|---|
| `BEACON_PRESENT` | ✓ strong | — |
| `BEACON_ABSENT` | — | weak only (−0.5 logit) |
| `CALENDAR_GUEST` | ✓ (windowed) | ✗ never |
| `DECLARE_PRESENT` | ✓ sticky | — |
| `DECLARE_ABSENT` | — | cancels sticky + small decay |
| `ALONE` | — | ✓ others, 10-min half-life, **s < 0.7 only** |
| `ALEXA_HINT` | ✓ | **NEVER — no negative code path exists** |
| `PRIVATE_NOW` (authenticated) | — | ✓ all others, 5-min window |

## Key semantics

- **Minimax:** `d* = min effective clearance over the credible set`. Person id →
  roles → 0 (fail closed). Corrupt depths raise loudly.
- **Budget cap:** `B(s) = 1 − 0.75·s`; weights `{4:1.0, 3:0.5, 2:0.2, 1:0.05, 0:0}`.
  Step `d*` down while any `hidden_from` listener would breach. d4 to a
  hidden_from listener is blocked as well as by clearance (belt and suspenders).
- **Decisions:** `d* ≥ 1` → SPEAK(d*); else owner credible → PHONE; else DEFER.
  PHONE/DEFER imply SPEAK(d0) shape-wise.
- **Empty credible set** (degenerate belief) → treated as unknown visitor,
  clearance 0 → fail closed. Pinned by test.
- **ALONE ignored** for items with sensitivity ≥ 0.7 (planner fuses twice).
- **Language-blind:** person IDs are opaque labels; rendition strings are never
  read. `test_properties.py::TestK4` proves decisions are invariant under
  rendition-language permutation.

## Running the tests

```
cd packages/hotlane/tests
PYTHONPATH=.:../.. python3 -m unittest discover -s .
```

89 tests: belief (24), credible (9), budgets (16), chain (13), planner (19),
properties (8: K1–K4 + negative controls). Evidence in `evidence/hotlane/`.
