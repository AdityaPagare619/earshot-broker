# J10 DESIGN — adversarial race & failure-injection harness

**Owner:** J10 (single-threaded). **Type:** Type-2 (test/docs harness; reversible,
no shared-code changes). The kernel (`packages/kernel/`) is FROZEN — this seat
does not patch it. Findings against shared code go to `docs/residual-risks.md`
with fix shapes, flagged for Petu.

## Problem

The kernel's 24 tests prove the single-threaded decision contract. Nobody has
proven what happens when the world moves *during* a release: audience changes
racing commits, leases redeemed against stale epochs, sensors dying mid-lease,
clocks lying, workers crashing. The dossier names these races (§11, blueprint
§6) but the closure mechanisms live in an unwritten arbiter layer. This seat
builds the adversarial evidence: a deterministic race harness, a fault injector,
an honest latency model, and a residual-risk register — every break a test,
every unfixable break a named risk.

## What ships

```
tests/races/
    arbiter.py          # Test-only authoritative release boundary (NOT production code):
                        #   epoch registry, grant store, serialization lock,
                        #   trusted clock, segment binding (epoch+seq+digest).
                        #   Exists to demonstrate F1: naive kernel use races,
                        #   arbiter-guarded use doesn't.
    test_epoch_commit_races.py     # F1: prepare/commit vs audience_changed interleavings
    test_lease_races.py            # F4/F5: replay, buffering, no-revoke, withdraw granularity
    test_sensor_races.py           # F6/F7: empty-audience, stale observed_at, heartbeat death
tests/failure-injection/
    faults.py           # Deterministic fault injector: kill_sensor, bump_policy,
                        # skew_clock, crash_renderer, timeout_calendar, revoke_capsule
    test_failure_injection.py      # F2/F3/F8/F9: each fault vs kernel behavior, asserted
    test_adversarial_inputs.py    # malicious-context suite: frozen now, forged observed_at,
                        # tenant confusion, incomplete derive dependencies, UNKNOWN in readers
docs/residual-risks.md  # Every unfixable break: mechanism, why unfixable here, fix shape, owner
docs/latency-model.md   # §11.3: measured kernel terms + labeled unmeasurable terms
evidence/
    latency.json        # measured p50/p99 per kernel op, N iterations, machine note
    race-matrix.md      # every race: interleaving, naive result, guarded result
```

## Decisions

1. **Deterministic interleavings, not sleeps.** Race tests drive two threads with
   explicit `threading.Event` turn-taking so the *adversarial* interleaving is
   forced, then assert the outcome. Each race has a control: naive kernel use
   must FAIL (leak/over-release), arbiter-guarded use must PASS. A race test that
   can't show both is theater (verdict anti-theater check).
2. **Arbiter is test scaffolding, labeled as such.** It demonstrates the *shape*
   of the missing production layer (epoch registry + serialization boundary +
   trusted clock + segment binding) without pretending to be it. It lives under
   `tests/`, imports only the frozen kernel, and its docstring says what
   production would need (single logical sequencer per room, §11.1).
3. **Faults are deterministic and enumerated.** `faults.py` exposes named faults
   (`kill_sensor()`, `skew_clock(dt)`, `bump_policy()`, `crash_renderer()`,
   `timeout_after_accept()`, `forge_context(...)`) applied at precise
   prepare/redeem boundaries. No random chaos — every fault is a reproducible
   scenario with an asserted kernel response.
4. **Latency: measure one term honestly, label four.** Measure kernel-op latency
   (prepare/redeem/projection/accept/open_private) p50/p99 over 20k iterations
   into `evidence/latency.json`. The §11.3 sum's other terms (undetected entry,
   sensing, transport, buffered audio) are labeled UNMEASURABLE-HERE with the
   reason each. One measured number beats five invented ones.
5. **No kernel patches from this seat.** F1–F10 findings against shared code are
   recorded in `docs/residual-risks.md` with mechanism + fix shape + suggested
   owner, and surfaced in the final report. Cross-seat patching without the
   owner's review is how races get *introduced*.

## Rejected alternatives

1. **Patching `kernel.py` directly** (add grant store, sequence numbers, trusted
   clock). Rejected: the kernel is the shared frozen contract — J3's server and
   J6's paired-world tests build on it. Unilateral changes fork the contract and
   void the 24-test baseline. Report, don't patch, across seat boundaries
   (principal-governance: contract is the coordination mechanism).
2. **Timing-based race tests** (`time.sleep` tuned so the interleaving "usually"
   hits). Rejected: flaky by construction, and a passing run proves nothing about
   the guarded path. Deterministic turn-taking or nothing (principal-mindset:
   don't fool yourself).
3. **A full chaos-monkey framework with random fault schedules.** Rejected:
   non-reproducible failures are unactionable in a 6-day competition window, and
   random schedules can't target the dossier's *named* races. Enumerated,
   deterministic faults mapped 1:1 to F1–F10 instead. (The randomness itch is
   real; the evidence it produces isn't.)

## Frozen contracts (this seat consumes, never changes)

- `packages/kernel/kernel.py` — Label/Fact/Context/Lease/Kernel API as-is.
- `packages/contracts/API_CONTRACTS.json` — the 4 tools; `withdraw_request`
  semantics ("cannot undo already emitted speech") bound the F5 test's
  expectations.
- Dossier §11.3 latency terms; blueprint §6 commit ordering (my arbiter
  implements exactly that pseudocode, so the race tests test the *blueprint*,
  not my invention).

## Failure modes of this seat's own work

- **Harness proves the arbiter, not production.** The arbiter is single-process
  with a Python lock; a distributed deployment needs the logical sequencer
  (§11.1). Labeled in the module docstring and the risk register.
- **GIL hides true parallelism.** Python threads + GIL mean my "races" are
  interleavings, not simultaneous execution. The turn-taking design makes this
  explicit: I test *orderings*, and orderings are where TOCTOU lives. True
  data races on C-level atomics are out of scope — labeled.
- **Latency numbers are machine-specific.** Recorded with machine note in
  `evidence/latency.json`; they bound the kernel term only.

## Honest boundaries

- No device integration, no real sensors, no audio pipeline — the "buffered
  audio" and "sensing delay" terms are labeled, never measured.
- No production-security claims. The register says what would be needed.
- Fixture data labeled fixture. ₹0 spent.

## Kill conditions

- If the deterministic interleavings cannot reproduce a naive-path failure for
  F1 after a genuine effort (i.e., the kernel already closes it — disproving my
  verdict), the F1 test becomes a *regression* test documenting the closure, and
  the verdict is amended on the record. Being wrong loudly beats being right
  quietly.
- If any test needs a sleep to pass, it's deleted, not tuned.
