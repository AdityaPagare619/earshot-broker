# J9 evidence — source adapters (`services/gateway/adapters/`)

Seat: J9 (adjacent-device exec). Branch: `seat/j09`. All fixture-only; ₹0.

## Test results (traceable)

| Suite | Command | Result |
|---|---|---|
| Kernel (unchanged) | `python3 -m unittest test_kernel` in `packages/kernel/` | 24/24 OK |
| Adapters v1→v3 | `python3 test_adapters.py` in `services/gateway/adapters/` | 43/43 OK (also clean under `-W error::ResourceWarning`) |

## What the 43 adapter tests prove

- **Contract enforcement (§3 as code):** `contract_check` passes for both
  adapters; a deliberately broken adapter (field without label) fails loudly.
- **Fail private:** unknown source → `UnsupportedSourceError` ("failing
  private"); duplicate registration rejected.
- **Private baseline:** every emitted kernel `Fact` has readers ⊆ {owner};
  no field is public by accident.
- **Busy-intervals-first:** `busy_intervals()` returns (start, end, status)
  only — test asserts titles/notes absent from the serialized output;
  declined/cancelled/transparent records excluded.
- **Recurrence:** DAILY/WEEKLY+COUNT/UNTIL/byweekday expand inside the window;
  MONTHLY/YEARLY → `RecurrenceError` → single flagged occurrence (never
  dropped, never infinite); COUNT is global per RRULE (documented by test).
- **DST:** all-day event across the 2026-11-01 US fallback keeps its calendar
  day; daily recurrence keeps 09:00 wall time across the transition.
- **Mutations:** `reschedule` declares attendee recipients + notification side
  effects and structurally forbids attendee/notification fields; task
  mutations declare zero external recipients; idempotency keys stable across
  title edits, change on etag bump.
- **Registry sync:** freshness TTL lifecycle, stale-version fail-closed,
  tombstone (calendar) and purge (tasks) deletion semantics.
- **Plan ops:** `validate_plan_ops` maps ops to adapters; unknown and
  ambiguous ops raise typed errors.
- **Generalization (the verdict's falsifiability test):** tasks adapter has
  zero imports from the calendar adapter and disjoint op sets; a third
  (notes) adapter registers against the frozen contract with no base-code
  change; adapter Facts are withheld from uncontrolled hosts by the real
  kernel (`room_projection` → empty).

## Honest boundaries (not tested / not claimed)

- Fixture providers only. No OAuth flows, no Google API calls, no network —
  `endpoint_allowlist` is `()` and there is no HTTP code path.
- Recurrence covers DAILY/WEEKLY; MONTHLY/YEARLY degrade to flagged single
  occurrences by design.
- No device integration (Fire TV / Ring / wearable) — the generalization
  claim is about the contract, demonstrated by two dissimilar sources.
- Full plan-AST validation is J3's area; `plan_ops.validate_plan_ops` is
  the adapter-side seam they can import.
