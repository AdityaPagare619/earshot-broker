# pro-quickstart — DESIGN.md

## The problem
The brief's non-negotiable #3: "clone → one command → the 5-beat demo runs and
the MCP server answers. Target: under 2 minutes on a fresh machine." Today there
is NO such command. A judge must assemble it from README + docs + tribal
knowledge (venv? pip install? which port? where's the dev token? what does the
initialize body look like?). Every manual step is a place a judge gives up.

## Two quickstart stories (coordination with pro-docs)
pro-docs' `docs/quickstart.md` (present in their worktree) documents Story A:

- **Story A — meet the product:** `python3 apps/personal/quickstart.py`
  (personal surface, <1s, "no installs"). VERIFIED BROKEN on the merged tree:
  `ModuleNotFoundError: No module named 'earshot'` without `pip install -e .`
  (quickstart.py only inserts the repo root; the package lives behind the
  package-dir mapping). Fix is in this lane (minimal bootstrap, additive);
  flagged to pro-cli who owns `apps/personal/`.

- **Story B — prove the install (this lane's script):** `quickstart.sh`
  venv → `pip install -e .` → `earshot-demo` → live `earshot-server` →
  real MCP handshake over HTTP → SUCCESS + timing. This is the professional
  install-verification story: it proves non-negotiables #1–#4 on a fresh
  machine with zero insider knowledge.

The two stories do not compete. A points at the product, B proves the
packaging. `docs/quickstart.md` should eventually link B; that edit belongs
to pro-docs (their file), noted in my report.

## quickstart.sh — step plan (timed budget)
| # | Step | Expected |
|---|------|----------|
| 0 | Preflight: `python3 --version` ≥ 3.10, `curl` present | ~1s |
| 1 | Create `.venv-quickstart` (reuse if valid → idempotent re-runs) | 5–10s cold |
| 2 | `pip install -e .` (stdlib-only: no wheels to fetch) | 10–20s cold |
| 3 | `earshot-demo` → expect `ALL 5 BEATS PASSED` | ~5s |
| 4 | Start `earshot-server --port 8000` in background, stderr→file, wait for port | ~2s |
| 5 | Extract dev token from stderr (`token=esh_dev_…` line the server prints by design) | <1s |
| 6 | `initialize` → HTTP 200 + `2025-11-25` in body; capture `Mcp-Session-Id` | ~1s |
| 7 | `notifications/initialized` → 202; `tools/list` → 200 + `prepare_day_brief` present | ~1s |
| 8 | Kill server, verify exit, print `QUICKSTART SUCCESS in Ns` | <1s |
**Budget: < 120s. Expected cold: ~40–60s. Warm (venv reused): ~15s.**

Failure behavior: `set -euo pipefail`; every step asserts its output
(`die` with the exact failed expectation). Port 8000 in use → die loudly
("port 8000 busy — another server running?") rather than silently picking
another port (a judge debugging "why is nothing on 8000" is worse).

## quickstart.ps1 — decision: YES, write it
The brief's judge has a Windows laptop. A careful, linear `.ps1` mirroring
the `.sh` step-for-step beats a manual block: the steps are mechanical
(`py -m venv`, `pip install`, `Start-Process`, `curl.exe` — all stock on
Win10+). Honest boundary: **I cannot execute PowerShell here** — the file is
marked `# UNTESTED ON WINDOWS — mirrors quickstart.sh; CI windows-latest
must run it` and the risk is stated, not hidden. Kept deliberately simple:
no advanced functions, no pipeline tricks.

## Risks
1. **Port contention with sibling lanes** running test servers concurrently
   (pro-tests hit this). Mitigation: preflight port check + loud death.
2. **Token extraction fragility** if pro-server changes the stderr format.
   Mitigation: grep for `token=esh_dev_` (the documented dev-token prefix),
   fail loudly if absent.
3. **`.ps1` untested** — stated in-file, not hidden.
4. **`apps/personal/quickstart.py` bootstrap fix** overlaps pro-cli's
   `apps/personal/` ownership. Kept minimal (path inserts only, no behavior
   change); flagged in report for the merge.

## kemiljk critic (pre-build)
- Semantics: script asserts real wire behavior (200/202 + body markers), not
  just exit codes — an exit-0 server that 401s everything would be theater.
- States: every failure path prints what was expected vs seen (empty/error
  states covered via `die`).
- Fit: entry-point names (`earshot-demo`, `earshot-server`) match
  `pyproject.toml [project.scripts]` — verified, not assumed.
