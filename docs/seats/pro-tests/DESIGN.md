# pro-tests — DESIGN

**Lane:** unified test invocation. **Goal:** `python -m pytest` from repo root runs ALL
~640 tests with zero env vars, on Linux/macOS/Windows, in CI.

## What exists today (the mess)

- 61 `test_*.py` files scattered across 17 directories (`tests/`, `packages/*/tests`,
  `services/**`, `apps/*/tests`, `packs/tests`, `integration/tests`).
- Each suite needs its own `PYTHONPATH` incantation (`tests/README.md` documents two;
  the rest lived in seat agents' heads). Per-file `sys.path.insert` hacks, some
  `os.path`-relative (robust), one CWD-relative (`..` in
  `services/gateway/mcp/tests/test_room_keep_secret.py` — breaks unless CWD is the test dir).
- **Two files hardcode a dead worktree path**
  (`/home/hatch/workspace/earshot-broker-trees/j07/...` in
  `packages/trace-harness/tests/fixtureserver.py` and `test_harness.py`). Worse than
  unportable: on this machine the stale j07 copy **shadows** the current
  `trace_harness` (it has no `slo/` subpackage), so `test_slo.py` **fails to import
  here today**. This is fixed in this lane (see §3).
- **True name collisions** (verified by experiment, not assumed):
  - `harness` = `services/gateway/mcp/tests/harness.py` vs `tests/failure_paths/harness.py`
    (6 test files each do plain `from harness import`).
  - `arbiter` = `apps/simulator/arbiter.py` (output arbiter) vs `tests/races/arbiter.py`
    (race scaffolding). Demonstrated: with both dirs on `sys.path`, races tests pick up
    the simulator's `Arbiter` → 9 errors (`'Arbiter' object has no attribute 'prepare_grant'`).
  - `sys.modules` caching means import *order* decides the winner — silent wrong-module
    bugs, not loud failures. A single unified runner MUST handle this explicitly.
- Test-file basename collisions: `test_gate.py` ×2, `test_pipeline.py` ×2 → pytest's
  default `prepend` import mode would alias them in `sys.modules` (second import silently
  returns the first module). **Requires `--import-mode=importlib`.**
- `services/gateway/config/tests/*.py` use package-relative imports (`from ..gate import`)
  → they must be imported under their fully-qualified name (`services.gateway.config...`),
  which importlib mode provides.

## Design

### 1. Root `conftest.py` — the single source of path truth

- Computes repo root as `Path(__file__).resolve().parent` (pathlib, cross-platform).
- Inserts, once, the **source** dirs (deduped, absolute): `packages/kernel`,
  `packages/` (for `hotlane`/`slowlane`/`secrecy`/`trace_harness` packages),
  `packages/hotlane/tests` (for `_helpers`), `services/gateway/adapters`,
  `services/gateway/mcp`, `tests/races`, `demo/`, and the repo root itself
  (for `packs.*`, `integration.*`, `tests.*` package-qualified imports).
- Deliberately does **NOT** add: `apps/simulator` (its tests self-insert; adding it would
  let the wrong `arbiter` win for races tests), `services/gateway/config` (would make
  top-level `gate` ambiguous — `packages/secrecy/gate.py` must win for
  `packages/secrecy/store.py`'s `from gate import MonotoneGate`), `integration/fixtures`
  (would make top-level `shape` ambiguous — `services/gateway/mcp/shape.py` must win).
- **Collision eviction:** every test module is collected as an `_EvictingModule`
  (via `pytest_pycollect_makemodule`), whose `_getobj` — the single import point —
  evicts the colliding top-level helper names from `sys.modules` *immediately
  before that module is imported*. The colliding set is computed repo-wide
  (stem → dirs, intersected with names test files import unqualified), not
  hardcoded: today `{arbiter, gate, harness, shape}`. The repo-wide scan matters
  because the collision isn't always "sibling helpers" — `apps/simulator/arbiter.py`
  is a *source* file colliding with `tests/races/arbiter.py`, which a
  sibling-dir-only scan misses. Evicting in `pytest_collect_file` was tried and
  does NOT work: pytest builds the whole collection tree before importing any
  module, so the eviction is stale by import time. Each test file's own-dir
  `sys.path.insert` then resolves its sibling helper. Already-imported modules
  keep their bound references, so this reproduces the old per-suite process
  isolation inside one process.
- **One-process port discipline:** suites previously ran in separate processes,
  so a leaked listening socket died with the process. In one process it
  survives and collides (found live: trace-harness's fixture server held 8899
  into mcp's `PORT+2`). Rule: every class that starts a server releases it in
  `tearDownClass` (`shutdown()` + `server_close()`). All networked suites use
  distinct localhost ports per file (8891/8892/8896/8897/8899/8900).
- **Dual-mode for pro-packaging:** if `import earshot` succeeds, conftest logs it and
  carries on — the path setup is purely additive and the old top-level names
  (`kernel`, `hotlane`, …) cannot collide with the `earshot` package. Works pre-packaging
  (fallback active, verified this lane) and post-packaging (no changes needed).

### 2. `pyproject.toml` — pytest configuration

`[tool.pytest.ini_options]`: `testpaths` (explicit dir list),
`python_files = ["test_*.py"]`, `--import-mode=importlib` via `addopts`
(`--import-mode` is CLI-only in pytest — no ini key exists).
Also `[project]` name/version stub + `[project.optional-dependencies] test = ["pytest"]`.

**pro-packaging coordination** (their `docs/seats/pro-packaging/DESIGN.md` §2, read
18 Oct): their lane converts all imports to absolute `earshot.*` and adds
`[tool.setuptools.package-dir]` + `[project.scripts]` to this same file — the
merge must keep both sections. Their contract is compatible with this design:
once `import earshot` works, conftest logs `packaged_mode=True` and the path
setup stays as a harmless additive fallback (old top-level names can't collide
with the `earshot` package). My per-test-file `sys.path.insert` lines are
test-only; their "never `sys.path.insert` in shipped code" rule is unaffected.
When they convert test files to `earshot.*` imports, the eviction hook simply
has less to do — no conftest change needed.

### 3. Test-file fixes (with reasons — nothing gratuitous)

1. `packages/trace-harness/tests/fixtureserver.py`, `test_harness.py`: replace hardcoded
   `/home/hatch/workspace/earshot-broker-trees/j07/...` inserts with
   `Path(__file__)`-relative computation. Reason: unportable; actively shadows current
   code with a stale copy on this machine (breaks `test_slo.py` today).
2. Twelve test files that import sibling helpers but have **no** own-dir insert get one
   (`sys.path.insert(0, dirname(abspath(__file__)))`):
   `tests/failure_paths/test_{deny_recovery,error_oracle,lease_lifecycle,paired_worlds,timing_parity,withdraw_reconcile}.py`,
   `services/gateway/mcp/tests/{test_tools,test_latency,test_protocol,test_constant_shape}.py`,
   `apps/simulator/tests/{test_gateway_port,test_mcp_client}.py`.
   Reason: without it, which helper they get depends on global path order or CWD —
   the exact fragility this lane eliminates. This matches the pattern most test files
   already use. No test logic touched.
3. Deleted `packages/trace-harness/tests/__init__.py` and `integration/tests/__init__.py`.
   Reason: under `--import-mode=importlib` pytest derives the module's dotted name from
   the `__init__.py` chain — both files create a phantom top-level `tests` package that
   collides with the repo-root `tests/` package (`No module named 'tests.test_harness'`).
   Neither is load-bearing (no package-qualified imports of either exist; old unittest
   runs imported them top-level). The repo-root `tests/__init__.py` stays —
   `tests/paired_world/harness.py` does `from tests.support.j06_report import …`.
4. `packages/trace-harness/tests/test_harness.py`: added the missing `tearDownClass`
   (`shutdown()` + `server_close()`). Reason: the fixture server's listening socket
   survived into later suites in the one-process run and collided with mcp's
   `PORT+2` (= 8899, `EADDRINUSE`); the old per-suite process exit had hidden the leak.
5. `tests/support/j06_report.py`: `flush()` no longer clobbers a real evidence file
   with an empty report. Reason: the atexit flush fires on collection-only runs too
   (`pytest --collect-only` imports modules without running tests) and was truncating
   `evidence/j06-*-report.json` to zero records.

`packages/kernel/` is **not** modified (frozen).

### 4. `tests/README.md`

Rewritten: one invocation, what it runs, how CI calls it, where to look when a suite fails.

### 5. What happens to `tests/failure_paths` special-casing

Gone. The old README's second invocation (`PYTHONPATH=...:tests/failure_paths`) existed
only because `test_*.py` there import sibling `harness` with no own-dir insert.
Fix §3.2 + conftest eviction subsume it. `tests/failure_paths/run_all.py` (J4's
evidence generator) is left untouched — it's a script, not the test path.

## Risks

- **One-process port/socket reuse:** every networked class must release its port
  in `tearDownClass` (shutdown + server_close); all ports are distinct per file
  (8891/8892/8896/8897/8899/8900 verified). Found and fixed live: trace-harness's
  fixture server leaked 8899 into mcp's `PORT+2` (see §3).
- **Timing-sensitive race tests:** `tests/races` (18 tests, ~5s) and `test_latency.py`
  passed standalone; full-run timing will be watched, not assumed.
- **pytest 8/9 API:** conftest subclasses `_pytest.python.Module` and replicates the
  default `pytest_pycollect_makemodule` construction
  (`Module.from_parent(parent, path=...)`) — the same call the default hook makes,
  so version drift risk is minimal; the test extra pins `pytest>=8`.
- **Windows:** conftest uses pathlib only; per-file hacks use `os.path` (portable);
  the two fixed files now use `pathlib` too. No POSIX-only calls in the test path
  (verified by grep for `os.fork|fcntl|signal.SIGKILL|/dev/`).

## Verification

- BEFORE: per-suite old-style runs, summed (see report).
- AFTER: `python -m pytest` from root → all green; `--collect-only` count ≥ BEFORE;
  per-file test counts spot-checked against BEFORE.
- kemiljk critic lens applied to conftest.py/pyproject/DESIGN.md before push.
