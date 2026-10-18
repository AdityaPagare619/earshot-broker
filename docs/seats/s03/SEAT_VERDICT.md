# SEAT VERDICT — S3: Constant Shape (Seam 3)

**Seat:** S3 · **Lens:** Seam 3 — "the room can't learn what it can't tell apart."
**Date:** 18 Oct 2026 · **Judge:** the S3 seat agent, before writing code.

## Verdict: the response path is not sealed-speech shaped — 5 named failures

The gateway is real, the auth is closed (R1), the arbiter stops output first. But
**nothing on the current wire is constant-shape.** The crown jewel of the final
architecture does not exist yet in code. That is this seat's entire job.

### F1 — `public_facts` is a variable-length list: the count is the leak (CRITICAL)
`prepare_day_brief` returns `{"request_ref", "request_state", "public_facts": [...]}`.
The list length is a function of hidden world contents. Today strict vs empty worlds
happen to return the same 2 public facts, so the existing paired-world tests pass —
but the SHAPE is secret-dependent in principle (a world with 5 public facts returns
5 items; a world with 1 returns 1). "One private item" was killed as a spoken
behavior; "N public items" is the same leak wearing a different coat. **The whole
`public_facts` array must die as a wire shape**, replaced by the response contract.

### F2 — the simulator speaks fixture lines, not tool responses (CRITICAL)
`host.py` `utter()` calls the tool, then briefs from `FIXTURES[mode]["briefing"]`
— hardcoded lines that never passed through any assembly. Worse, the lines
themselves violate constant shape: "strict" says **"You have 3 flexible tasks
today"** (a COUNT) and "relaxed" says **"One private item — sent to your phone"**
(the EXISTENCE leak the synthesis explicitly killed in Step 8). The UI path
bypasses the seam entirely. The demo is shape-theater until the UI speaks what the
assembler produced.

### F3 — no cover-mode concept in the response path (MAJOR)
There is no `mode`, no fixed suffix, no `speak_policy`, no `followups`, no
`screen_depth`, no `_meta`. Nothing distinguishes "owner alone" from "mom present"
in the response — because nothing in the response was ever *planned* against an
audience. The probe branch in `utter()` is keyword matching ("private" in text),
not a constant-shape guarantee: it returns "I can't help with that on this
speaker" — a DIFFERENT denial shape than any other response, which is itself a
probe-distinguishable oracle.

### F4 — the paired-world tests can't catch the count leak (MAJOR)
`test_paired_world.py` is good structure (full bodies, ref normalized) but it
compares a shape that still contains counts, and it has no negative control: there
is no test proving the suite would FAIL if a leak existed. A privacy test that
can't fail is theater (J7's rule). It also lacks the add-guest counterfactual —
the test that proves listener counts don't leak either.

### F5 — no chunked turns, no "next" (MINOR)
`followups` doesn't exist. Long briefings are single-shot; there is no turn
boundary at which a mid-conversation audience change can collapse the disclosure.
The honest version of "mid-stream collapse" (chunked turns, each "next" re-reading
belief) is entirely absent.

## What's strong (keep, extend, don't fork)
- **R1 auth closure** (J3): identity from the credential, idempotency keyed by
  (tenant, owner, key). My response contract inherits this untouched.
- **The harness** (`tests/harness.py`): real server in a thread, real HTTP. My
  wire-level paired-world tests extend it.
- **`strict_world(secret_title=...)`**: the fixture already parameterizes the
  secret — the prenatal→therapy counterfactual is one argument away.
- **The arbiter** (J2): stop-output-first, per-segment grants. My chunker composes
  with it — chunks are planned per turn, segments are gated per chunk.
- **J4-C3**: unknown vs forbidden → byte-identical "unavailable". My probe
  responses follow the same indistinguishability discipline.

## What I will NOT do (lane discipline)
- I will not build S2's planner (belief fusion, minimax, budgets). I define the
  assembler's input contract and ship a **fixture planner** against the frozen
  dataclasses; S2 replaces it without touching the assembler.
- I will not add `room` / `keep_secret` tools (S4's lane). The response contract
  I define is the shape S4's tools will return.
- I will not touch `packages/kernel/` (frozen), the auth layer, or the transport.
- I will not "fix" the `day_card` resource's `public_facts` list — it's a resource,
  not the tool response path. Noted as an observation for the broker owner: its
  list length is public-fact-count-dependent. Out of my lane.

## Confidence
90% that F1–F3 are the correct highest-risk findings for Seam 3, and that replacing
`public_facts` (not layering alongside it) is the honest fix. Layering would
preserve the exact leak the seam exists to kill.
