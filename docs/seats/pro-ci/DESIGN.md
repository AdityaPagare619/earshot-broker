# pro-ci — DESIGN

**Lane:** CI that proves the professional claims.
**Branch:** `pro/pro-ci` · **Worktree:** `~/workspace/earshot-pro-trees/pro-ci`
**Target:** the NEW public repo layout defined in `PRO_MIGRATION_BRIEF.md` (this CI is
written for that layout, not for the current `packages/`/`services/` tree).

## What "green" means

1. `pip install -e .` succeeds on **ubuntu-latest, windows-latest, macos-latest** ×
   **Python 3.10, 3.11, 3.12** — 9 combinations, every one of them.
2. `python -m pytest` from repo root runs the **entire unified suite with zero
   PYTHONPATH hacks** and exits 0 on all 9 combinations.
3. A stdlib-only lint (byte-compile of every `.py` file) passes.
4. On Windows specifically, the `earshot-demo` console entry point runs to completion
   (exit 0) — because the judge's laptop is the riskiest surface.
5. **No fake green, ever:** no `|| true`, no `continue-on-error` on the test job,
   no `if: always()` masking. A red test is a red build. `fail-fast: false` so one
   broken cell doesn't hide the other eight.

## The matrix

| Axis | Values | Why |
|---|---|---|
| `os` | `ubuntu-latest`, `windows-latest`, `macos-latest` | Brief non-negotiable #2: cross-platform is the feature |
| `python-version` | `3.10`, `3.11`, `3.12` | 3.10 = lowest supported (broadest judge compatibility); 3.12 = current; 3.13 excluded deliberately — too new for some judge laptops, and stdlib-only code gains nothing from it |

9 cells. `fail-fast: false`.

## Jobs

| Job | Runs on | Does |
|---|---|---|
| `test` | matrix (9 cells) | checkout → setup-python → `pip install -e .` → `pip install pytest==<pin>` → `python -m pytest`. Env: `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` (Windows console encoding is the classic cross-platform test killer). |
| `lint` | ubuntu-latest, py3.12 | `python -m compileall` over the repo (stdlib only, zero new deps). Layout-agnostic by design — compiles every `.py` outside `.git/`. |
| `smoke-windows` | windows-latest, py3.12 | `pip install -e .` then runs the `earshot-demo` entry point end-to-end. Proves the 2-minute judge story on the riskiest OS. |

Plus principal-grade hygiene: top-level `permissions: contents: read`, `concurrency`
with `cancel-in-progress` (don't burn minutes on superseded pushes), `timeout-minutes`
on every job, pip caching via `setup-python`.

## Assumptions (explicit, because the other lanes haven't landed)

1. **pro-packaging** will produce `pyproject.toml` at root with `[project.scripts]`
   entry points `earshot-demo`, `earshot-server`, `earshot-sim`, stdlib-only
   dependencies. If packaging instead emits a `requirements-test.txt`, the pytest
   install line moves there — one-line change, noted in the YAML comment.
2. **pro-tests** will unify the suite so `python -m pytest` from root collects
   everything (currently the suites need per-package `PYTHONPATH` invocations —
   the brief explicitly kills that). The workflow does **not** set `PYTHONPATH`;
   if tests need it, the build is red by design, which is the honest signal.
3. **pytest is a CI-only dependency**, pinned (`pytest==8.3.4`). It is NOT a package
   dependency — the `earshot` package itself stays stdlib-only per the brief.
   Pinning is deliberate: unpinned CI is how "green yesterday, red today" happens.
4. **pro-windows** owns `pathlib`/POSIX-only fixes; CI's job is to *catch* what
   they miss, not to fix it. The `smoke-windows` job is the backstop.
5. `demo/`'s 5-beat runner stays non-interactive and exits 0 on success (it is today:
   `demo/five_beats.py --lang en`). The smoke job trusts the exit code only.

## Risks

- **R1 — Layout drift.** If the merged repo's layout differs from the brief's target
  (`src/earshot/`, `tests/`, `demo/`), paths in `lint` still hold (layout-agnostic),
  but `pip install -e .` is the load-bearing assumption. Mitigation: this DESIGN.md
  names the assumption; Petu's merge verification runs the workflow file against the
  merged tree before accepting.
- **R2 — pytest collection surprises.** 464 tests written for unittest-discovery may
  behave differently under pytest (import modes, fixtures). That's pro-tests' lane;
  CI reports whatever pytest reports — honestly.
- **R3 — Windows socket/port flakiness** in future server-smoke additions. Current
  scope is the demo entry point only; a server smoke is a recommended follow-up,
  not smuggled into this lane half-tested.

## Critic log (kemiljk ai-output-judgement, applied before shipping)

Reviewed the workflow against the rubric, not the preview:

- **F1 — branch pushes got no CI.** First draft had `push.branches: [main]`; with 20+
  lanes pushing to `pro/*`, that meant no CI on the pushes that matter. Fixed:
  `push` on all branches (concurrency group cancels superseded runs, so cost is bounded).
- **F2 — pip never upgraded.** Old runner images ship ancient pip; `pip install pytest`
  can fail on wheel resolution. Fixed: `python -m pip install --upgrade pip` first
  in both install jobs.
- **Checked, kept:** `actions/checkout@v4` / `setup-python@v5` current majors;
  `pytest==8.3.4` is a real pinned release; `python -m` invocations (not bare `pip`)
  for Windows correctness; `fail-fast: false`; `contents: read`; timeouts on all jobs;
  `PYTHONUTF8`/`PYTHONIOENCODING` for the Windows console-encoding failure mode.

## What I deliberately did NOT do

- No `continue-on-error`, no `|| true`, no output parsing that could mask failures.
- No test sharding/caching tricks that trade clarity for speed — 464 stdlib tests
  are fast; the matrix is the honest cost.
- No `3.13` in the matrix (see table) and no `macos-13`-style runner pins that rot.
- No Codecov/badges theater — the Devpost judge cares that tests run, not that a
  badge is green.
