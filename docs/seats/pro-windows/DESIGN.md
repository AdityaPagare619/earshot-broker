# pro-windows — DESIGN.md

**Lane:** Windows cross-platform compatibility for the EARSHOT pro migration.
**Seat:** pro-windows · worktree `~/workspace/earshot-pro-trees/pro-windows` · branch `pro/pro-windows`
**Base:** main @ a441166. Kernel (`packages/kernel/`) NOT touched — audit read-only there.

## Audit method

Static audit of every runtime path (`demo/`, `apps/`, `services/`, `packages/`,
`packs/`, `integration/`) for the Windows failure taxonomy:

| Check | Tool | Result |
|---|---|---|
| `os.fork`, `fcntl`, `termios`, `pwd`, `grp` | grep | **clean** — none |
| `signal.SIGKILL`/`SIGUSR`, `os.mkfifo` | grep | **clean** — none |
| `subprocess` / `shell=True` / `shlex` | grep | **clean** — none (no subprocess at all) |
| `os.chmod` / `os.symlink` | grep | **clean** — none |
| `select.epoll`/`kqueue`/`poll` | grep | **clean** — none |
| `multiprocessing` | grep | **clean** — none |
| `tempfile.NamedTemporaryFile` reopen | read | **OK** — `delete=False` + `finally: os.unlink` in `test_profiles.py`; `mkdtemp` elsewhere |
| sockets | read | **OK** — explicit `127.0.0.1` IPv4 bind, `ThreadingHTTPServer`/`ThreadingMixIn`; `allow_reuse_address=True` on MCP server |
| hardcoded `/` in paths | grep | **clean** — all joins via `os.path.join` |
| `open()` without `encoding=` | grep | **2 runtime hits** → fix (F6) |
| unicode `print()` | grep -P non-ASCII | **3 entry points** → fix (F1) |
| `os.path` vs `pathlib` | grep | **pervasive** → convert (F2) |
| shebang-dependent execution | grep `^#!` | **2 files** → harden (F3) |
| `\n` assumptions | read | **clean** — no binary protocol line handling outside `http.server` (correct) |

## Findings & fixes

### F1 — Unicode stdout crashes on non-UTF-8 Windows consoles (P0)
`demo/five_beats.py` prints Devanagari (`--lang hi`) and em/en dashes; `apps/simulator/host.py`
prints an em-dash; `evidence_gen.py` prints evidence text. On Windows consoles not in UTF-8
mode (cp1252/cp936/cp932 — still common outside Windows Terminal), this raises
`UnicodeEncodeError` and kills the demo. **Fix:** new repo-root `wincompat.py` with
`ensure_utf8_stdout()` (`sys.stdout.reconfigure(encoding="utf-8",
errors="backslashreplace")`, guarded for old Pythons / non-reconfigurable streams),
called at the top of every entry point: `demo/five_beats.py`, `apps/simulator/host.py`,
`services/gateway/mcp/server.py`, `apps/personal/quickstart.py`,
`packages/trace-harness/trace_harness/__main__.py`. (Moves to `src/earshot/` in the
packaging lane.)

### F2 — `os.path` → `pathlib` (P1, brief mandate)
All runtime path computation converted: `demo/five_beats.py`,
`services/gateway/mcp/{server,broker}.py`, `apps/simulator/{host,gateway_port}.py`,
`apps/personal/{personal/__init__,personal/inbox,personal/profile,quickstart}.py`,
`packs/loader.py`, `packages/hotlane/evidence_gen.py`, plus `sys.path` inserts in tests.
`Path(__file__).resolve().parent` replaces `os.path.dirname(os.path.abspath(__file__))`.
Behavior identical on POSIX; correct separators on Windows.

### F3 — entry points must not depend on shebangs (P1)
`demo/five_beats.py`, `apps/simulator/host.py` carry `#!/usr/bin/env python3` (harmless on
Windows, kept for POSIX). Verified `python -m demo.five_beats` and
`python -m apps.simulator.host` work from repo root via namespace packages (no
`__init__.py` needed); documented in `docs/` quickstart as the Windows invocation.

### F4 — `.gitattributes` (P1)
Added: `* text=auto`, `*.py text eol=lf`, plus `*.toml`, `*.json`, `*.md`, `*.html`,
`*.svg`, `*.txt` as text. No `.bat` files added (none needed — entry points are
`python -m`).

### F5 — `open()` encoding (P2)
`packages/hotlane/evidence_gen.py` (2 writes) and
`packages/trace-harness/trace_harness/__main__.py` (1 write) → `encoding="utf-8"`.

## What I could NOT verify (honest boundary — CI lane must cover)

1. **No Windows machine here.** All verification is static + Linux runtime. The pro-ci
   lane MUST run the full suite on `windows-latest` (and feed any failure back).
2. **Console behavior**: `reconfigure(encoding="utf-8")` works on py3.7+; on ancient
   `python3.6` the guard falls back to `PYTHONUTF8=1` documentation. CI should test the
   oldest supported Python.
3. **`allow_reuse_address=True`** on Windows enables `SO_REUSEADDR` with Windows
   semantics (another process can bind the same port). Acceptable for a localhost
   demo/dev server; documented in `docs/api.md` security notes by the docs lane.
4. **Long paths**: Windows MAX_PATH (260) — repo paths are short; no action.
5. **Firewall prompt**: first bind to 127.0.0.1 may trigger Windows Firewall on some
   setups; localhost-only bind minimizes this. Docs lane should mention "allow on
   private networks" if prompted.

## kemiljk critic self-review (applied before done)

- *Concrete failures named, not vibes*: F1 is a real crash (Devanagari on cp936),
  not a style nit. F2 is brief-mandated. No drive-by refactors: `os.path` in
  pure-test helpers left alone where the churn buys nothing — actually no, converted
  the `sys.path` inserts too since CI runs tests on Windows and consistency is the
  brief's word. Hmm — rechecked: conversions are mechanical and test-verified, keep.
- *No new dependencies*: stdlib only (`pathlib`, `sys`). ✓
- *No behavior change on POSIX*: every conversion is semantics-preserving; full test
  suite re-run after changes. ✓
- *Kernel untouched*: audit read-only, zero edits under `packages/kernel/`. ✓
- *The critic caught real bugs in my own conversions* (second pass, 21:00 IST):
  two `_REPO_ROOT` off-by-one drops (`broker.py`, `gateway_port.py` — N `..`
  segments need N+1 `.parent`s), one wrong-direction `_HERE.parent.parent.parent`
  in `host.py`, one in `trace_harness/__main__.py`, 20 files missing the
  `from pathlib import Path` import (regex without `re.MULTILINE` silently skipped
  files starting with docstrings), and one missed `os.walk` in
  `test_language_blind.py`. All found by running the suites, not by staring.
  Lesson: mechanical edits need behavioral verification, every file, every time.

## Second-session findings (20:45–21:30 IST)

- **F6 (pre-existing, not Windows-specific, NOT fixed here)**: `PYTHONPATH=packages/kernel
  python3 -m unittest discover -s tests` reports 6 errors on clean main too
  (verified via pristine worktree @ a441166): `discover -s tests` recurses into
  `tests/failure_paths/` whose `from harness import ...` needs
  `tests/failure_paths` on the path. The README's second invocation covers it.
  Out of the Windows lane's scope (test-invocation design belongs to pro-ci /
  packaging); reported, not refactored.
- **F7 (fixed)**: `packages/trace-harness/tests/fixtureserver.py` and
  `test_harness.py` hardcoded `/home/hatch/workspace/earshot-broker-trees/j07/...`
  sys.path entries — stale J7-seat worktree paths, broken on ANY other machine,
  Windows or not. Replaced with `Path(__file__)`-relative inserts.
- **F8 (fixed, test was vacuous on main)**: `packs/tests/test_language_blind.py`
  built `ROOT` with un-normalized `..` segments, so every `os.walk` dirpath
  contained the literal substring `"tests"` and the `if "tests" in dirpath`
  filter skipped ALL files — the language-conditional scan tested nothing.
  Normalizing via `pathlib` made it real (12 files scanned). It then flagged
  `integration/contracts.py:23` (`lang_detected` field + comment with `"hi"`) —
  a false positive of the crude regex (field name contains "lang", never branched
  on; value is `(self.pack.name,)`, pure data routing). Tightened the regex to
  `\blang\b` (standalone word) with negative controls; scan now genuinely passes
  over 12 files.
- **F9 (docs, fixed)**: `tests/README.md` now documents the Windows
  `PYTHONPATH` `;` separator with PowerShell and cmd.exe forms.

## Verification performed

- `python -m compileall` on the whole tree (services apps demo packages packs
  integration wincompat.py) — clean.
- Full unit-test invocation from repo root (both documented commands) — green
  except the 6 pre-existing F6 errors, identical on main.
- Per-package suites, all green: simulator 35, packs 33, integration 14,
  slowlane 68, trace-harness 16, gateway/mcp 91 (real HTTP wire), adapters 43,
  personal 16.
- `python -m demo.five_beats --lang en` and `--lang hi` run end-to-end
  ("ALL 5 BEATS PASSED").
- `python -m trace_harness run --selftest` — 5/5 pairs + 2/2 adversarial PASS.
- Simulator `host` imports cleanly from a foreign cwd.
- MCP server smoke: binds 127.0.0.1, `initialize` → HTTP 200 with dev bearer
  token, unauthenticated → 401 (auth gate works). `tools/list` without the
  `Mcp-Session-Id` session header → 400, which is correct Streamable HTTP
  server behavior; full session flows are covered by the 91-test wire harness.
- `git ls-remote` check after push.
