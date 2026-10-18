# pro-cli DESIGN.md — personal surface as a first-class installed CLI

## Who this is for

The **device owner** (Priya in the fixture story; the judge in the demo story).
She is the only person who may ever see sealed content, approve a plan, or change
declassification settings. The personal surface is her private window into EARSHOT:
onboard once, keep an inbox of sealed requests, open the exact plan, preview what
each audience would hear, approve digests, and run the counterfactual proof that
the boundary holds.

## The 90-second story (judge with a Windows laptop)

```bash
pip install -e .
earshot personal-quickstart --fresh     # 7-step onboarding, day brief, preview, proof, HTML report
earshot personal inbox                  # sealed inbox: receipts only, never content
earshot personal open <ref>             # exact plan + sealed facts (owner only)
earshot personal preview <ref>          # what public / room / personal each see
earshot personal prove <ref>            # counterfactual: hidden content changes, public doesn't
```

No `cd apps/personal`, no `PYTHONPATH`, no `python3 -m personal.cli`. One install,
one command family.

## What changes

1. **`earshot.personal` becomes an installed package.** pro-packaging mapped every
   other surface but left `apps/personal/` out (flagged out-of-scope). This lane adds:
   - `"earshot.personal"` to `[tool.setuptools] packages`
   - `"earshot.personal" = "apps/personal/personal"` to `[tool.setuptools.package-dir]`
2. **Import contract compliance.** `from kernel import …` → `from earshot.kernel import …`
   in `fixture_calendar.py`, `inbox.py`, `preview.py`. All `sys.path` bootstraps die:
   `personal/__init__.py` (the `_bootstrap()` hack), `cli.py`'s `__main__` insert,
   `quickstart.py`'s two inserts, `tests/test_personal.py`'s insert.
3. **Entry points.** `earshot` dispatcher gains `personal` and `personal-quickstart`
   subcommands; a dedicated `earshot-personal` console script is added (mirrors
   `earshot-demo` / `earshot-server` / `earshot-sim`). `quickstart.py:main()` gains
   an `argv=None` parameter so it works as an entry point (currently `main()` takes
   no args — a latent bug for installed use).
4. **Stale invocation strings updated.** Every user-facing "run: python3 quickstart.py"
   becomes `earshot personal-quickstart`; `python3 -m personal.cli` docstrings become
   `earshot personal …`. `prog=` becomes `earshot-personal`.
5. **Error quality.** No tracebacks on user error: missing profile → one-line "run
   onboarding first" + exit 2; bad `--set` → usage line; unknown ref → "Unavailable"
   (deliberate — indistinguishable from a permission failure, per the threat model).

## What does NOT change

- Kernel FROZEN — untouched, only imported.
- The 7 onboarding steps, profile schema v1, fixture-grade auth labels, the
  counterfactual proof semantics, the HTML report. Behavior-preserving refactor.
- `preview.py` imports `_fact_from_event` and `PUBLIC_WEATHER` from `.inbox`
  (private-name import across modules — kept; it's intra-package, not a contract).

## Risks

- **R1 — `earshot.personal` vs old `personal` shadowing.** After install, both the
  installed `earshot.personal` and a stray `personal` on sys.path could coexist.
  Mitigation: every import in the package is absolute `earshot.personal.*` or
  relative; tests import `earshot.personal.*` only. The old top-level `personal`
  name is never added to sys.path by our code again.
- **R2 — conftest collision.** Root conftest.py deliberately avoids adding
  `apps/personal` (its tests self-contained). After conversion, `test_personal.py`
  imports `earshot.personal` (installed) — no path hack needed. Verified by running
  the suite.
- **R3 — `quickstart.py` argv.** Changing `main()` → `main(argv=None)`; the
  `if __name__ == "__main__"` path passes `sys.argv[1:]`. Entry point
  `earshot-personal-quickstart`? NO — keeping the surface tight: dispatcher
  subcommand `personal-quickstart` + script stays runnable. (One fewer name to
  document; the dispatcher is the primary UX.)

## Verification

- `python -m pytest apps/personal` → 16/16 green.
- `python -m pytest` (root) → full suite count unchanged, zero new failures.
- Fresh venv: `pip install -e .`, then from a foreign cwd (`/tmp`):
  `earshot personal-quickstart --fresh`, `earshot personal inbox`,
  `earshot-personal --help`, `earshot --help` lists both new commands.
- Windows-static: no new os.path, no new prints of unguarded unicode
  (quickstart already calls ensure_utf8_stdout at import).

## kemiljk critic

Read `kemiljk_ai-output-judgement/SKILL.md` before shipping; judge the CLI's
help output and error paths part-by-part as a first-time user would see them.
