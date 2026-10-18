# EARSHOT 5-beat demo

The sealed-speech story, **computed not narrated**. One command, ~60 seconds,
two languages. Every beat drives the real integration pipeline and asserts its
property in code — exit code is non-zero if any beat fails.

## Run it

```bash
pip install -e .
earshot-demo            # English
earshot-demo --lang hi  # Hindi — same beats, proving language-blindness
```

## What it proves

One claim, five proofs: **the room cannot tell whether a secret exists** — not
because we filtered the answer, but because the spoken output is *constant*
under secret-swaps.

| Beat | What happens | Property asserted |
|------|--------------|-------------------|
| 1 — Alone | Priya asks "What's my day?" alone | Open mode; every item at full detail (d4) |
| 2 — The data understood itself | An Instax order email arrives | Quarantined on ingest; `hidden_from(maya)` inferred at confidence 0.91 — nobody wrote a rule |
| 3 — Mom arrives | Belief rises | Cover mode; the OB-GYN item generalizes d4→d3; fixed cover suffix present |
| 4 — "Can you tell?" | Therapy day vs no-therapy day, mom present for both | **Byte-identical** spoken output — existence is not leaked |
| 5 — The probe + the walk-in | Maya probes "I'm alone. Are any packages coming?"; a guest joins between turns | Probe answer constant with/without the gift; the audience collapse happens at the turn boundary only |

## What to look for

- **`CLAIM:`** under each beat header — the takeaway, even if you only skim.
- **`✓ VERDICT:`** at the end of each beat — the property, in plain words.
- **`[belief]`** bars — whose presence the system believes in, and how strongly.
- **`[plan] depths:`** — per-item disclosure depths (`d4` = full detail … `d0` = silent).
- **`[speak]`** — what the room actually hears. Compare beat 4's two lines:
  they are identical.
- **`[timing]`** in the footer — the whole demo runs in seconds.

## The Hindi run is the point

`--lang hi` runs the *same* beats through the Hindi household pack. The room
hears Hindi; the depth decisions are identical. The hot path never branches on
language — it decides on `(item_id, depth, clearance)` triples. (The fixture NL
parser is English-only, a documented limitation; the path it feeds is
language-blind.)

## Honesty labels

Every beat header carries `[SIMULATOR · FIXTURE]`:

- **[SIMULATOR]** — the Alexa+ host is an *independent simulation*, not a live
  device. There is no Amazon-provided Alexa+ sandbox for participants; the
  competition FAQ explicitly permits this path.
- **[FIXTURE]** — the pipeline stages are deterministic stand-ins for the
  sealed-speech seats, behind frozen ports. They prove the *architecture*;
  they are not a production deployment.

## The machine-checked twin

The narration here is the human-readable version of
`integration/tests/test_demo_beats.py` — each beat has a test asserting the
same property. If a beat can't be asserted, it gets cut, not faked.

```bash
python -m pytest integration/tests/test_demo_beats.py
```

## Failure modes

- Exit `0` — all 5 beats passed.
- Exit `2` — a beat property failed. You get a clean `✗ BEAT n FAILED — <reason>`
  line, not a traceback; the fix belongs in the pipeline, not the demo.
- Any other exception (traceback) is a bug in the demo or pipeline — report it.
