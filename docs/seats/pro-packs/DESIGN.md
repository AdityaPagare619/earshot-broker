# pro-packs — DESIGN.md

## Lane
Own `docs/packs.md` (Household Pack authoring guide) + a real `packs/validate.py`
validator entry point. Base: main @ c422bae.

## What exists (do not reinvent)
- `packs/schema.py` — frozen schema, already fails loudly (`PackError` with file/line).
  `validate_pack()` validates base packs fully; lang packs get manifest + file-split
  checks; lexicon/renditions/ui cross-validation happens inside `load_pack()`.
- `packs/loader.py` — `load_pack(packs_root, lang)` is the full validation path:
  base + lang, inherit-chain check, lexicon-vs-taxonomy check. The ONLY code that
  knows languages exist.
- `packs/yaml_subset.py` — dumb, dependency-free YAML-subset parser. Deliberate:
  pack files must be auditable by humans, not require PyYAML.
- 33 tests green (`test_pack_conformance.py` 27 incl. broken-pack mutations,
  `test_language_blind.py` 6). I keep all green; I add none (validator is verified
  by live mutation runs, documented below — adding committed broken-pack fixtures
  would ship broken packs in the repo, which is exactly what we must not do).

## What is missing (the gap this lane closes)
1. **No authoring guide.** A stranger who wants a third language (say, Marathi)
   has only the YAML files and the schema docstrings. `docs/packs.md` must take
   them from zero to a validated pack, including the *why* behind each file.
2. **No standalone validator.** Today validation only runs inside tests or at
   load time. A pack author needs `earshot-validate-pack` — run it, get PASS/FAIL
   per file, exit 1 on any violation, with file:line context. This is also what a
   judge runs to prove the "10 broken-pack mutations fail loudly" claim.
3. **The leak-verifier story is tribal knowledge.** During S6, the pack's own
   slowlane leak verifier fired twice on pack *data*: (a) a `{category}` placeholder
   in d3 templates rendered the sensitive topic "therapy" into speech; (b) a
   Latin-only gift regex missed Devanagari/Hinglish terms. Both fixed in data, not
   code. The guide must tell this story — it is the proof that "packs are data,
   and data gets policed."

## Design decisions
- **Validator = thin CLI over existing contracts.** `packs/validate.py::main()`
  calls `validate_pack()` (base + each lang) then `load_pack()` per lang
  (cross-file checks). Zero new validation logic — new logic would be a second
  source of truth. The CLI adds: per-pack reporting, exit codes, human-readable
  failure output (`PackError` already carries file/line).
- **Entry point** `earshot-validate-pack = "earshot.packs.validate:main"` added to
  pyproject `[project.scripts]` (next to the other four). `python -m` also works
  via `if __name__ == "__main__"`.
- **Default target** = the shipped packs dir (resolved via `importlib.resources`
  with repo-tree fallback, same pattern as the demo runner). `--root DIR`
  overrides for third-party packs. `--lang xx` validates one language; default
  validates base + every lang dir found.
- **Mutations are ephemeral.** The 3 broken-pack demonstrations run in `tempfile`
  dirs and are never committed. Broken packs must never exist in the repo —
  not even as fixtures.
- **Guide structure** (docs/packs.md): what a pack is (data, not code) →
  file map → the frozen schema (domains table) → authoring a new language,
  step by step → the validator → the leak-verifier story (therapy + gift regex)
  → what the loader guarantees downstream (language-blind contract) →
  what NOT to do (anti-patterns).

## Risks
- **Scope creep into schema changes.** The schema is frozen. If the guide wants a
  new field, the answer is no — document the constraint instead.
- **pyproject edit conflicts** with sibling lanes. The scripts table is
  append-only; my one-line addition merges cleanly.
- **Windows:** validator uses pathlib + utf-8 everywhere; no new POSIX surface.
  `tempfile` for mutations is Windows-safe.

## Verification
1. `earshot-validate-pack` → base/en/hi all PASS, exit 0.
2. 3 temp-dir mutations (unknown placeholder; lexicon topic not in taxonomy;
   missing required role) → each exit 1 with file:line error.
3. 33 pack tests green; full `python -m pytest` green.
4. kemiljk self-critique before push.
