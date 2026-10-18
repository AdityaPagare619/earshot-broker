# pro-demo — DESIGN.md

**Author:** pro-demo (principal demo engineer)
**Date:** 2026-10-18
**Scope:** `demo/` only — presentation polish of `five_beats.py` + new `demo/README.md`.
No pipeline changes. No kernel contact.

## 1. The demo's job

A Devpost judge has 90 seconds and a Windows laptop. The demo must prove, in one
terminal command, the single claim that separates EARSHOT from every "smart
filter" entry:

> **The room cannot tell whether the secret exists** — not because we filtered
> the answer, but because the spoken output is *constant* under secret-swaps.

Sixty seconds, five beats, two languages. Each beat is a *computed* property
(asserted in code, exit non-zero on failure), not narration. The tests in
`integration/tests/test_demo_beats.py` are the machine-checkable twin of the
narration — if a beat can't be asserted, it gets cut (K2), not faked.

## 2. What the 5 beats prove (unchanged semantics)

| Beat | Setup | Property asserted |
|------|-------|-------------------|
| 1 — Alone | Priya alone | Open mode, every item d4, no cover suffix |
| 2 — The data understood itself | Gift email ingested | Quarantined on ingest; `hidden_from(maya)` inferred at conf ≥ 0.6, no human rule |
| 3 — Mom arrives | `room("mom's here")` | Cover mode; OB-GYN generalizes d4→d3; fixed cover suffix present |
| 4 — "Can you tell?" | Therapy day vs no-therapy day, mom present | **Byte-identical** `speak` — existence is not leaked |
| 5 — The probe + the walk-in | Maya: "I'm alone. Are any packages coming?" + guest joins mid-demo | Probe answer constant with/without gift; collapse happens at the turn boundary only |

## 3. UX problems in the current runner (concrete, not vibes)

1. **Beat markers are flat.** `--- BEAT 1 [0:00–0:30] — Alone ---` reads like a log
   line. A judge scanning output can't tell where one claim ends and the next
   begins. Fix: numbered block headers with a claim line ("WHAT THIS PROVES:")
   and a verdict line ("✓ VERDICT: ...") so each beat is skimmable even if the
   middle scrolls past.
2. **[SIMULATOR][FIXTURE] labels are present but not unmissable.** They appear in
   the banner and the final line. A screenshot of the middle beats shows no
   honesty label. Fix: repeat a compact `[SIMULATOR · FIXTURE]` tag on every
   beat header. Honesty must survive cropping.
3. **No timing summary.** The brief's judge story is "under 2 minutes" but the
   runner never says how long it took. Fix: per-beat elapsed + total at the end.
4. **Failure messages are assertion tracebacks.** `assert resp.speak == ...,
   "BEAT 4 FAILED..."` — an AssertionError traceback is the opposite of a clean
   failure message for a judge. Fix: wrap the beat bodies so a failed property
   prints `✗ BEAT n FAILED — <one-line reason>` plus a hint (e.g. "see
   integration/tests/test_demo_beats.py"), then exit 2. No traceback for
   *expected* failures (a failed beat property). Unexpected exceptions (bugs)
   still show tracebacks — that's correct, they're not expected.
5. **`--lang` exists but is undiscoverable.** Fix: README + `--help` epilog
   pointing at the Hindi run as the language-blindness proof.
6. **No README.** `demo/` has no entry point documentation. Fix: `demo/README.md`.

## 4. What I will NOT change

- Pipeline behavior, beat order, beat properties, assertion conditions.
- `STRINGS`, `build_day()`, `BEAT_TIMES` — all referenced by
  `integration/tests/test_demo_beats.py`. Signatures frozen.
- The `[SIMULATOR] [FIXTURE]` honesty semantics — only made louder.
- `main(argv)` returns int; entry point `earshot-demo` unchanged.

## 5. Implementation plan

1. Add a `_Beat` runner: `run_beat(n, title, claim, fn)` that times `fn`,
   catches `BeatFailed` (raised via a `fail(reason)` helper replacing bare
   asserts), prints the verdict line, and records elapsed.
2. Beat bodies become small functions; each ends with an explicit verdict
   print (already present as `[verdict]` lines — promote to `✓` lines).
3. `fail()` raises `BeatFailed`; `main()` catches it → clean `✗` message → `return 2`.
4. Header: keep the `=` banner, add the one-line claim of the whole demo.
5. Footer: per-beat timings + total + `ALL 5 BEATS PASSED [SIMULATOR] [FIXTURE]`.
6. `demo/README.md`: what each beat proves, how to run (`earshot-demo`,
   `--lang hi`), what to look for, honesty labels explained, link to
   `integration/tests/test_demo_beats.py` as the machine-checked twin.
7. Run: `earshot-demo --lang en`, `earshot-demo --lang hi` (from installed
   entry point), plus `python -m pytest integration/tests/test_demo_beats.py`.

## 6. Risks

- **Refactoring beat bodies into functions** could subtly change execution order
  or variable scoping. Mitigation: keep bodies verbatim, only re-indent; run
  the beat tests before/after.
- **Windows console**: `✓`/`✗`/`█` glyphs — `ensure_utf8_stdout()` is already
  wired (pro-windows); keep `errors="backslashreplace"` fallback in mind and
  avoid any other exotic glyphs.
- **Timing noise**: per-beat timings are informational only, never asserted.

## 7. kemiljk critic plan (after build)

Judge the *terminal output* part-by-part as a human judge would: (a) banner —
does the claim land in 3 seconds? (b) beat headers — skimmable? (c) verdict
lines — is the property stated in plain words? (d) footer — timing + honesty
present? (e) failure path — run with a deliberately broken assertion, check the
`✗` message has no traceback. Fix, re-run, re-verify.
