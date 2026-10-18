# pro-packaging — DESIGN.md

**Lane:** packaging · **Branch:** `pro/pro-packaging` · **Engineer:** pro-packaging (principal, Python packaging)
**Goal:** `pip install -e .` → `import earshot` works; `earshot-demo` / `earshot-server` /
`earshot-sim` / `earshot` entry points work; all 464+ tests stay green; Windows/macOS/Linux.

## 1. The core decision: package-dir mapping, NOT file moves

Two options were on the table:

| | A. Move files into `src/earshot/` now | B. setuptools `package-dir` mapping (chosen) |
|---|---|---|
| Kernel frozen constraint | Moving `packages/kernel/` = touching it — forbidden | Kernel stays put; re-exposed via shim |
| B-lane coordination | Steps on B lane's "src/ layout migration" | B lane's moves become **import-neutral** (see §3) |
| Risk | High — every seat's paths/tests shift at once | Low — files don't move, only imports change |

**Chosen: B.** All internal imports are converted to **absolute `earshot.*`** form now.
When B lane later moves files into `src/earshot/`, the imports do not change —
the mapping entries are simply deleted. The import contract below is therefore
stable across the migration, which is the whole point of a contract.

## 2. The import contract (law for all lanes)

After `pip install -e .`, these MUST resolve. B lane: keep these paths working.

```
earshot                        # top-level package; __version__; light __init__ (no heavy imports)
earshot.kernel                 # MODULE (shim) re-exporting the FROZEN packages/kernel/kernel.py
                               # exposes: Kernel, Fact, Label, Context, Lease, PUBLIC
earshot.slowlane               # packages/slowlane/      (quarantine, verifier, compiler)
earshot.hotlane                # packages/hotlane/       (belief, credible, planner, budgets)
earshot.secrecy                # packages/secrecy/       (edges, gate, store, declarations, overrides, parse)
earshot.gateway                # services/gateway/       (namespace package)
earshot.gateway.mcp            # services/gateway/mcp/   (server, broker, auth, fixtures, shape)
earshot.gateway.adapters       # services/gateway/adapters/ (contract, calendar_adapter, tasks_adapter)
earshot.gateway.config         # services/gateway/config/   (profiles, gate, readiness)
earshot.simulator              # apps/simulator/         (host, arbiter, audience, gateway_port, mcp_client)
earshot.packs                  # packs/                  (loader, schema, yaml_subset + data files)
earshot.integration            # integration/            (pipeline, ports, contracts)
earshot.integration.fixtures   # integration/fixtures/   (sealed-task fixtures)
earshot.trace_harness          # packages/trace-harness/trace_harness/ (capture, differ, normalize, worlds, adapters)
earshot.trace_harness.slo      # packages/trace-harness/trace_harness/slo/ (SLO lab)
earshot.demo                   # demo/                   (five_beats)
earshot.cli                    # src/earshot/cli.py      (entry-point functions)
```

**Rules:**
- Within a package: **relative** imports (`from .edges import SecrecyEdge`).
- Across packages: **absolute** (`from earshot.kernel import Kernel`). Never top-level
  (`from kernel import`), never `sys.path.insert` in shipped code or test files —
  with ONE documented exception: `tests/failure-injection/test_failure_injection.py`
  inserts its own dir because `faults.py` lives in a hyphenated directory that can
  never be a dotted package name.
- **One module family.** Never mix `earshot.packs.*` and source-tree `packs.*` in one
  process — they are distinct module objects (different `PackError` classes, etc.).
  Every import of shipped code goes through `earshot.*`, including inside test files.
- Test-helper imports (not shipped): absolute against the source tree —
  `from tests.failure_paths.harness import …`, `from hotlane.tests._helpers import …`,
  `from tests.races.arbiter import …`. Rationale: they resolve identically under
  `pytest` and legacy `unittest discover`, unlike relative imports.
- Hyphenated dirs (`packages/trace-harness/`, `tests/failure-injection/`) can never
  appear in a dotted name. Their test modules import as top-level (pytest inserts the
  basedir); helpers there are imported top-level (`import fixtureserver`).
  `packages/trace-harness/tests/` deliberately has NO `__init__.py`: giving it one
  would claim the top-level `tests` package name and shadow the root `tests/`
  under pytest's prepend import mode (found the hard way — `No module named 'tests.races'`).
- `packages/kernel/` is FROZEN: no `__init__.py` added, no edits, no moves. Re-exposed only.
- stdlib only. Zero dependencies — `pyproject.toml` has no `dependencies`.

pyproject mapping (setuptools):
```toml
[tool.setuptools.package-dir]
"earshot" = "src/earshot"          # __init__.py, cli.py, kernel.py (shim), __main__.py
"earshot.slowlane"       = "packages/slowlane"
"earshot.hotlane"        = "packages/hotlane"
"earshot.secrecy"        = "packages/secrecy"
"earshot.gateway"        = "services/gateway"
"earshot.gateway.mcp"    = "services/gateway/mcp"
"earshot.gateway.adapters" = "services/gateway/adapters"
"earshot.gateway.config" = "services/gateway/config"
"earshot.simulator"      = "apps/simulator"
"earshot.packs"          = "packs"
"earshot.integration"    = "integration"
"earshot.trace_harness"  = "packages/trace-harness/trace_harness"
"earshot.demo"           = "demo"
# earshot.integration.fixtures and earshot.trace_harness.slo resolve
# automatically relative to their mapped parents.
```

## 3. Kernel re-exposure (frozen, untouched)

`src/earshot/kernel.py` is a **module shim** (not a package — no `__init__.py` is added
to `packages/kernel/`). It locates `<repo>/packages/kernel/kernel.py` relative to the
installed `earshot` package (robust for `pip install -e .` and source checkouts —
the documented install story), loads it with `importlib.util.spec_from_file_location`,
and re-exports `Kernel, Fact, Label, Context, Lease`. If the frozen file is absent
(non-editable install without the source tree), it raises `ImportError` with an
actionable message. No `exec()` of source text; no duplication of the frozen file.

## 4. Entry points (`[project.scripts]` — no shebangs, Windows-safe)

```toml
earshot-demo   = "earshot.demo.five_beats:main"     # 5-beat sealed-speech demo (<60s)
earshot-server = "earshot.gateway.mcp.server:main"  # real MCP server (new main() added; was __main__-only)
earshot-sim    = "earshot.simulator.host:main"      # controlled web host (honesty banner)
earshot        = "earshot.cli:main"                 # help + subcommand dispatcher
```

`server.py` gains a `main(argv=None)` (argparse `--port`, default 8000) — the only
code addition to a shipped module, minimal and additive. `python -m earshot` also works.

## 5. Packs data

`packs/{base,en,hi}/**` ship as `package-data` under `earshot.packs`. The loader
resolves the data dir via `importlib.resources.files("earshot.packs")` with a
repo-relative fallback, so `load_pack` works installed or from source. (`\n`
handling: text mode with explicit `encoding="utf-8"`; no POSIX-only calls.)

## 6. Cross-platform

- `[project.scripts]` generates `.exe` shims on Windows — no shebang dependence.
- All path handling via `pathlib`/`os.path`; no `os.chmod`, no `fcntl`, no POSIX-only.
- `zoneinfo` is stdlib (3.9+); `requires-python = >=3.10`.
- CI (separate lane) runs `pytest` on ubuntu/windows/macos.

## 7. Tests

- All 600 tests (+64 subtests) pass. Test files are converted to `earshot.*` imports alongside
  sources (mechanical, same rule). This removes the `PYTHONPATH=packages/kernel`
  hacks: after `pip install -e .`, `python -m pytest` from repo root collects
  everything with no env vars — which is brief non-negotiable #4, achieved as a
  side effect of the import conversion.
- Old invocations (`PYTHONPATH=... python -m unittest discover`) keep working too,
  because absolute imports resolve whenever `earshot` is importable. Verified:
  `python -m unittest discover -s tests` → 109 OK; per-suite discovers OK.
- Kernel tests (`packages/kernel/test_kernel.py`) are NOT modified (frozen area);
  they keep their current invocation (24/24 green).
- **Port discipline** (learned making the single-`pytest` run green): test HTTP servers
  use fixed ports; the full run exposed two latent collisions —
  `test_room_keep_secret`'s `PORT+2` hit trace-harness's `:8899`, and my renumber
  then hit `test_paired_world`'s `:8893-:8895`. Fix: `test_room_keep_secret` moved to
  `:8893-:8895`… then `test_paired_world`'s teardown was fixed instead — every mcp
  `tearDownClass` now calls `harness.stop_server()` (`shutdown()` + `server_close()`),
  because `shutdown()` alone leaves the socket bound and poisons later binds.
  Current allocation: 8891 protocol, 8892 tools, 8893-95 paired_world,
  8896 latency, 8899 trace-harness fixture, 8900 constant_shape, 8902-04 room_keep_secret.
  New HTTP test servers: pick a fresh port ≥ 8905 and add teardown via `stop_server`.

## 8. Risks

1. **A missed top-level import** → `ImportError` at runtime. Mitigation: after conversion,
   `grep -rn "sys.path.insert" --include=*.py` (shipped code) must be empty; full suite green.
2. **Circular imports** via the new absolute paths (e.g. `earshot.mcp` ↔ `earshot.simulator`).
   Mitigation: `earshot/__init__.py` imports NOTHING heavy; smoke-test every entry point.
3. **B-lane drift**: if B lane renames a contract path, entry points break. Mitigation:
   this contract is the coordination artifact; B lane signs off on it.
4. **Wheel installs** (`pip install earshot` non-editable): the kernel shim needs the
   source tree. Documented limitation in README; the judge story is `pip install -e .`
   from a clone. Future work: bundle the frozen kernel as package data.
