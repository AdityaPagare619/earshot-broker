# Contributing to EARSHOT

Thanks for considering a contribution. This project is a hackathon entry built
like production software: the bar is high, the rules are written down, and
reviews are honest. If something here is unclear, open an issue — a confusing
contributing guide is a bug.

## The three rules that surprise people

Read these before anything else. They are the reason most first PRs get sent back.

1. **Stdlib only. Zero dependencies.** `pyproject.toml` has `dependencies = []`
   and it stays that way. If you believe you need a dependency, open an issue
   first and prove that the stdlib cannot do it. "It's easier with X" is not proof.
2. **The kernel is frozen.** `packages/kernel/` is never modified — not for
   features, not for "small fixes." It is the trust anchor: 24 tests pin its
   behavior, and every privacy claim in this repo rests on it. If you think the
   kernel is wrong, open an issue; the fix, if accepted, goes through the same
   adversarial review the kernel itself survived.
3. **DESIGN.md first for anything bigger than a typo.** Non-trivial changes start
   as a short design note (`docs/seats/<your-topic>/DESIGN.md`): what, why,
   what you will not touch, risks. Code before design gets closed.

## Getting started

Prerequisites: Python 3.10+ and git. Nothing else — no Docker, no cloud, no keys.

```bash
git clone https://github.com/AdityaPagare619/earshot-broker.git
cd earshot-broker
python -m venv .venv
# Windows: .venv\Scripts\activate  |  macOS/Linux: source .venv/bin/activate
pip install -e ".[test]"
```

Prove your setup works (under 2 minutes):

```bash
python -m pytest -q        # the whole suite: 640 tests + 64 subtests, ~30s
earshot-demo --lang en     # the 5-beat demo; ends with "ALL 5 BEATS PASSED"
```

If either fails on a clean clone, that's a bug in the repo, not in your setup —
please report it.

## How to contribute

- **Bug reports:** use the bug template. Include a repro, your OS and Python
  version, and — this matters here — whether the behavior involves the
  simulator or fixture data (see the honesty section of the README).
- **Ideas / feature requests:** use the feature template. This project designs
  *mechanisms that limit entire problem classes*, not instance-by-instance
  fixes — frame the problem class, not just your case.
- **Code:** fork, branch, PR against `main`. Keep PRs small and single-purpose.
  One PR = one change a reviewer can hold in their head.

## PR checklist (also in the PR template)

- [ ] `python -m pytest` green from the repo root — no new failures, no
      skipped-without-reason tests.
- [ ] No new dependencies (`pip freeze` diff is empty of additions).
- [ ] `packages/kernel/` untouched (or the change went through kernel review).
- [ ] Honesty preserved: new behavior is labeled simulated/fixture where it is;
      no claim added without evidence under `evidence/`.
- [ ] Docs updated if behavior changed (`docs/`, README, or CHANGELOG under
      `[Unreleased]`).

## Code conventions

- **Cross-platform or it doesn't ship.** `pathlib` for paths, `encoding="utf-8"`
  on every text file operation, no POSIX-only modules. CI runs
  ubuntu/windows/macos — your PR runs there too.
- **Imports:** absolute `earshot.*` across packages, relative within a package.
  No `sys.path` manipulation in shipped code. (One documented exception exists
  for hyphenated test-helper directories; don't add new ones.)
- **Tests prove the negative.** A privacy test that cannot fail is theater:
  every new guarantee needs an adversarial case *and* a negative control
  showing the test actually detects violations. See `tests/` for the pattern.
- **Windows console:** user-facing output must survive cp1252 — call
  `ensure_utf8_stdout()` at the top of any new entry point
  (see `earshot/wincompat.py`).

## What happens to your PR

A maintainer reviews for correctness, test coverage, and honesty of claims.
Expect direct feedback — "this test can't fail, make it adversarial" is a
normal review comment here, not a rejection of you. Small, well-tested PRs
merge fast; big, untested ones don't merge at all.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
