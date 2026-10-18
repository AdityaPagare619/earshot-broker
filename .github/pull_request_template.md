<!-- Keep it small, keep it honest. One PR = one change a reviewer can hold in their head. -->

## What

<!-- One paragraph: what does this change, and why? Link the issue if there is one. -->

## Merge bar

- [ ] `python -m pytest` green from the repo root — no new failures, no unexplained skips
- [ ] No new dependencies (`dependencies` in `pyproject.toml` still `[]`)
- [ ] `packages/kernel/` untouched — or the change went through kernel review (say which)
- [ ] Honesty preserved: simulated/fixture behavior still labeled; no new claim without evidence under `evidence/`
- [ ] Docs updated (README, `docs/`, or CHANGELOG `[Unreleased]` — or "no doc impact", and why)

## Tests

<!-- What did you run? Paste the summary line. For privacy behavior: name the
     adversarial case AND the negative control that proves the test can fail. -->

## Risks

<!-- What could this break? What did you deliberately not handle? -->
