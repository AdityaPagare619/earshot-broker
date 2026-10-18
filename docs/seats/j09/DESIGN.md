# DESIGN — J9: `services/gateway/adapters/`

Owner: J9 (single-threaded). Type: Type-2 (reversible internal library) with a
Type-1-adjacent frozen contract surface (the §3 declaration schema other seats
build against — J3's server, J1's deployment profiles). The contract schema is
frozen after this doc; implementations may iterate behind it.

## Problem

Blueprint §3 and dossier §8.4 specify a source adapter contract in prose. No code
exists. Without a coded contract, the first adapter sets precedent by hand-wiring
and EARSHOT stays a calendar tool. My area: make the contract executable, ship
the calendar adapter, and prove generalization with a second adapter
(tasks/reminders) that shares the kernel, the tools, and the contract — with zero
calendar code in its path.

## Decisions

**D1. Contract as declared data + pure functions, not a framework.**
`SourceAdapter` is an abstract base class whose subclasses declare the §3 items
as class-level data (provider id, endpoint allowlist, scopes, schemas, subjects,
label defaults, transformations, mutation recipients, idempotency policy,
freshness, deletion semantics) and implement four pure operations:
`normalize(raw) -> Record`, `label(record) -> Label`, `plan_ops() ->
frozenset[str]`, `mutation_impact(op) -> MutationImpact`. Shared logic
(recurrence expansion, busy-interval derivation, label joining) lives in
`common.py` as pure functions, never in a base-class method that subclasses
override. Composition over inheritance — the verdict's anti-fork requirement.

**D2. Labels are kernel Labels; private defaults are code, not docs.**
Every adapter declares `field_labels: {field: Label}` with a private baseline
per blueprint pipeline B step 4. `label()` joins field labels with
`Label.join` (kernel semantics: readers intersect). No field is ever public by
accident: the registry's contract-completeness check fails any adapter with an
undeclared field at import time.

**D3. Busy-intervals-first ingestion.**
The calendar adapter's default read path is `busy_intervals(range)` —
structured (start, end, status) with no titles/attendees. Full details require
an explicitly declared purpose (`details_for(purpose)`), logged in the
materialization record. This is the blueprint's least-privilege posture made
mechanical, and it directly answers "why not just fetch everything."

**D4. Registry fails private, typed.**
`AdapterRegistry.get(source_id)` raises `UnsupportedSourceError` for unknown
sources. The error is typed and loud; the gateway contract (J3) must map it to
"request proceeds with zero facts from that source," never to best-effort
public. A test asserts the exception type and that no facts leak.

**D5. Mutation impact is declared per op.**
Each adapter declares, per supported mutation op, the possible external
recipients (e.g. calendar time-change → attendees get notifications; task
check-off → no external recipient). `mutation_impact()` returns this; the plan
validator (J3's area; I provide the descriptor) can reject undisclosed
recipients. Time-only calendar changes are constrained by construction: the
`reschedule` op descriptor forbids attendee/notification fields.

**D6. Bounded recurrence in stdlib, tested to the edges.**
No `dateutil` (₹0, stdlib-only). `expand_recurrence()` handles DAILY/WEEKLY
with COUNT/UNTIL inside a bounded [start, end) window, timezone-aware via
`zoneinfo`, all-day events as date (not datetime) ranges. Unbounded or
unsupported rules raise `RecurrenceError` → the event materializes as its
single master occurrence, labeled, with a `recurrence_unsupported` flag —
never silently dropped, never infinitely expanded.

**D7. Tasks adapter: different domain, same contract.**
Tasks have no attendees, no locations, no recurrence (due dates + optional
repeat handled as new-task generation, declared); mutation recipients are
task-list-scoped (no external humans notified); freshness is poll-based with a
declared TTL (no webhooks). It emits kernel Facts with its own topics
(`tasks`, `health` for medication) and serves `load_flexible_tasks` from the
blueprint AST. Zero imports from `calendar_adapter`.

## Frozen contract (what other seats build against)

```python
class SourceAdapter(abc.ABC):
    provider_id: str                    # e.g. "fixture-calendar-v1"
    endpoint_allowlist: tuple[str, ...] # fixed; empty = fixture-only
    oauth_scopes: tuple[str, ...]
    record_schema: dict                 # field -> python type name
    subjects: tuple[str, ...]           # data subjects incl. owner
    field_labels: dict[str, Label]      # kernel Label; private baseline
    supported_transformations: tuple[str, ...]  # bounded, named
    mutation_recipients: dict[str, tuple[str, ...]]  # op -> recipients
    freshness_ttl_s: float
    deletion_semantics: str             # "tombstone" | "purge" | ...

    @abc.abstractmethod
    def normalize(self, raw: dict) -> "Record": ...
    @abc.abstractmethod
    def label(self, record: "Record") -> Label: ...
    @abc.abstractmethod
    def plan_ops(self) -> frozenset: ...          # e.g. {"load_busy_intervals"}
    @abc.abstractmethod
    def mutation_impact(self, op: str) -> "MutationImpact": ...
```

`Record` is a frozen dataclass: `source, external_id, version(etag),
fields: Mapping[str, str], derived: Mapping[str, str]`.
Registry: `register(adapter)`, `get(source_id) -> SourceAdapter`
(raises `UnsupportedSourceError`), `contract_check(adapter)` (raises
`ContractViolation` on any undeclared §3 item).

## Rejected alternatives

**R1. Universal JSON adapter with a label map.** One adapter ingesting arbitrary
records + a per-source label config. Rejected: dossier §8.4 kills it explicitly
— domain semantics (declined vs canceled, all-day vs timed, attendee
notification side effects) cannot be inferred from JSON shapes, and a malicious
or buggy source config could relabel clinical records as public. Explicit
adapters are the security boundary; the config *is* the adapter, reviewed as code.

**R2. Deep inheritance: `BaseAdapter` with overridable hooks.**
`CalendarAdapter(BaseAdapter)` overriding `fetch()`, `parse()`,
`label_fields()`. Rejected: fragile-base-class — the second adapter inherits
behavior it didn't ask for (my verdict's "polite fork" failure). The base class
here declares the contract and owns *no* behavior; all shared logic is in
`common.py` pure functions the adapters call explicitly.

**R3. Fetch-full-then-filter at release time.** Simpler ingestion (one code
path), privacy enforced at the release kernel. Rejected: violates
least-privilege (blueprint: busy intervals when they suffice), widens the
blast radius of a release-kernel bug to full record contents, and forfeits the
strongest demonstrable claim — "the private title never left the provider."
Ingestion minimalism is defense in depth, not premature optimization.

## Failure modes & mitigations

| Failure | Mitigation |
|---|---|
| Adapter declares a field with no label | `contract_check` fails at import; registry refuses |
| Recurrence rule unbounded/unsupported | `RecurrenceError` → single master occurrence + flag; never infinite |
| Source returns 429/5xx mid-sync | declared retry policy; sync result marked partial with `freshness_stale` |
| Record deleted upstream | tombstone/purge per `deletion_semantics`; dependent plans invalidated via version check |
| Unknown source requested | `UnsupportedSourceError`; gateway proceeds with zero facts (fail private) |
| Time-only change mutates attendees | `reschedule` descriptor excludes attendee/notification fields by construction |
| Timezone/DST edge (all-day, fold) | `zoneinfo`; all-day as date ranges; tests on DST transition days |

## Honest boundaries

- Fixture providers only (`fixture-calendar-v1`, `fixture-tasks-v1`); no OAuth,
  no Google API calls, no network. Endpoint allowlists are declared empty and
  enforced.
- No real sensors, no device integration (Fire TV/Ring/wearable are
  generalization *arguments*, not integrations — stated in the verdict).
- Recurrence covers DAILY/WEEKLY with COUNT/UNTIL; MONTHLY/YEARLY raise
  `RecurrenceError` → flagged single occurrence (documented, tested).
- The plan-AST validator is J3's area; I ship op descriptors + a minimal
  `validate_ops()` helper they can import. Flagged in my report.

## Pre-mortem (top 3)

1. *The tasks adapter secretly depends on calendar semantics* (e.g. reuses
   "busy interval" thinking for due dates) → the generalization test is
   theater. Mitigation: the cross-adapter test asserts zero imports and
   disjoint op sets; due dates modeled as deadlines, not intervals.
2. *A third source can't be added without touching base code* → contract
   incomplete. Mitigation: the "third adapter" test adds a minimal notes
   adapter in the test file itself against the frozen contract.
3. *Label defaults drift from docs* → silent over-sharing. Mitigation:
   contract check + a test that every emitted Fact's readers ⊆ declared
   subjects.

## Done-checklist (principal-systems §4)

- 10× sources: registry is a dict; contract check is O(fields). Yes.
- Provider down 4h: declared retry + `freshness_stale`; plans carry source
  versions and must regenerate before mutation. Yes.
- Junior misconfigures labels: contract check fails loudly at import. Yes.
- Junior halts bad adapter: registry `unregister`/flag; no deploy needed
  (config-level). Yes.
- Global vs local: the contract is the global win; per-adapter cleverness
  kept minimal. Yes.
- Run from docs: DESIGN.md + docstrings + tests. Yes.
