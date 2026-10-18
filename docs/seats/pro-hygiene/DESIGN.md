# pro-hygiene — DESIGN.md

## Sweep method
1. **Artifact check**: `find` for `__pycache__`/`.pyc`/`.orig`/`.rej`/`*~`/`.bak`/empty dirs; `git ls-files` for tracked junk.
2. **Link check**: script over all 64 markdown files resolving every relative link — 0 broken.
3. **Dead-code check**: `coverage run -m pytest` + import-reference grep. Coverage alone is
   UNRELIABLE here (wire tests spawn real HTTP servers in subprocesses; demo/entry
   points run out-of-process), so a file is "provably dead" only if: not imported by
   anything (grep), not an entry point (`pyproject.toml` scripts / `__main__` / documented
   CLI), not the provenance of a cited evidence file, AND (broken or superseded).
4. **tests/README.md**: checked — pro-tests already rewrote it; current and accurate. No action.

## Findings
| Item | Verdict |
|---|---|
| `__pycache__` / `.pyc` | 0 present, 0 tracked. Already clean. |
| Backup files / empty dirs | None. |
| Broken md links | 0 / 64 files. |
| `tests/failure_paths/run_all.py` | **DELETE** — provably dead: broken under the new layout (6 loader errors, finds 34/37 tests), superseded by `python -m pytest tests/failure_paths`, unreferenced except historical seat docs. |
| `tests/races/measure_latency.py` | KEEP — provenance of cited `evidence/latency.json`; works (uses `earshot.*`). |
| `services/gateway/config/__main__.py` | KEEP — documented operator CLI (`python -m services.gateway.config --check`). |
| `services/gateway/mcp/fixtures.py` | KEEP — imported by `broker.py` + `integration/pipeline.py`. |
| `integration/*` 0% coverage | Measurement artifact (subprocess/import-mode), all imported. KEEP. |
| `docs/seats/` + `docs/dossier/` | LEAVE — pro-docs owns the migration exclusion list. |
| `evidence/` raw logs | LEAVE — pro-evidence owns curation. |
| Function-level dead code | NOT attempted — coverage is unreliable here; guessing violates the lane bar. |

## .gitignore changes
Add IDE (`.idea/`, `.vscode/`), OS (`Thumbs.db`), coverage (`.coverage`, `htmlcov/`), build
(`build/`, `dist/`, `*.egg`), tool caches (`.hypothesis/`, `.mypy_cache/`, `.ruff_cache/`).
Remove the stray `# pytest one-command runs` comment line. `*.log` deliberately NOT added —
`evidence/` carries committed logs and pro-evidence owns that decision.

## Risks
- Deleting `run_all.py`: if any external doc/script calls it, it breaks. Mitigation: grepped
  repo-wide; only historical seat docs mention it, and they describe the J4 seat, not a live command.
- .gitignore additions only affect untracked files; zero risk to tracked content.
