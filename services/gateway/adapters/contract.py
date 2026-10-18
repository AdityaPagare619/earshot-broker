"""Executable source-adapter contract (dossier §8.4, blueprint §3).

Every adapter declares the §3 items as class-level data and implements four
pure operations. The base class owns NO behavior — shared logic lives in
``common.py`` as pure functions the adapters call explicitly. This keeps the
second (and third) adapter a config-level addition, not a fork.

The kernel is the labeling authority: adapters emit ``kernel.Fact`` objects
whose ``Label`` values come from ``field_labels`` joined with ``Label.join``.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import FrozenSet, Mapping

from kernel import Fact, Label

# Deletion behaviors an adapter may declare (blueprint §3).
DELETION_SEMANTICS = frozenset({"tombstone", "purge", "provider_managed"})


class AdapterError(Exception):
    """Base for all adapter failures. Never silently degrades to public."""


class UnsupportedSourceError(AdapterError):
    """Raised by the registry for unknown sources.

    The gateway must map this to 'proceed with zero facts from that source'
    (fail private) — never to best-effort public.
    """


class ContractViolation(AdapterError):
    """An adapter's §3 declaration is incomplete or inconsistent."""


class RecurrenceError(AdapterError):
    """A recurrence rule cannot be expanded as declared."""


@dataclass(frozen=True)
class Record:
    """A normalized provider record. All values are strings; parsing of
    datetimes happens in ``derived`` so the raw record stays inspectable."""
    source: str
    external_id: str
    version: str  # ETag / revision; plans pin this, stale plans regenerate.
    fields: Mapping[str, str]
    derived: Mapping[str, str] = field(default_factory=dict)
    subjects: FrozenSet[str] = frozenset()  # owner + other data subjects


@dataclass(frozen=True)
class MutationImpact:
    """Declared blast radius of one mutation op (blueprint §3)."""
    op: str
    recipients: FrozenSet[str]       # who outside EARSHOT can observe this
    side_effects: FrozenSet[str]     # e.g. {"attendee_notification"}
    idempotency_key_fields: tuple    # fields forming the idempotency key
    forbidden_fields: FrozenSet[str] = frozenset()  # must not change in this op


class SourceAdapter(abc.ABC):
    """Abstract §3 contract. Subclasses declare data; implement 4 operations."""

    # --- §3 declaration (class-level data; all required) ---
    provider_id: str
    endpoint_allowlist: tuple        # fixed; () means fixture-only, no network
    oauth_scopes: tuple              # minimal scopes, declared even for fixtures
    record_schema: dict              # field name -> python type name
    subject_kinds: tuple             # e.g. ("owner", "attendee")
    field_labels: dict               # field name -> kernel Label (private baseline)
    supported_transformations: tuple  # bounded, named (e.g. "busy_intervals")
    mutation_recipients: dict        # mutation op -> tuple of recipient kinds
    freshness_ttl_s: float
    deletion_semantics: str          # one of DELETION_SEMANTICS

    # --- four pure operations ---
    @abc.abstractmethod
    def normalize(self, raw: dict) -> Record:
        """Provider/fixture record -> normalized Record. Raises AdapterError
        on malformed input; never guesses missing fields."""

    @abc.abstractmethod
    def label(self, record: Record) -> Label:
        """Label for a normalized record: join of field labels. Private
        baseline; declassification is a separate, explicit step."""

    @abc.abstractmethod
    def plan_ops(self) -> frozenset:
        """Typed-plan operators this adapter serves (blueprint §4)."""

    @abc.abstractmethod
    def mutation_impact(self, op: str) -> MutationImpact:
        """Blast radius of a mutation op. Unknown op -> AdapterError."""

    # --- shared helpers (final; not overridable behavior) ---
    def facts(self, record: Record) -> tuple:
        """Emit one kernel Fact per declared field, labeled via label()."""
        lbl = self.label(record)
        return tuple(
            Fact(f"{self.provider_id}:{record.external_id}:{name}",
                 str(value), lbl)
            for name, value in record.fields.items()
        )

    def idempotency_key(self, op: str, record: Record) -> str:
        impact = self.mutation_impact(op)
        parts = [str(record.fields.get(f, record.derived.get(f, "")))
                 for f in impact.idempotency_key_fields]
        return f"{self.provider_id}:{op}:" + "|".join(parts)


class AdapterRegistry:
    """Source-id -> adapter. Unknown sources fail private, typed and loud.

    Also tracks per-record versions and sync times so the gateway can
    enforce freshness (blueprint §3) and deletion semantics (pipeline B
    step 10: invalidate affected plans on updates or deletion).
    """

    def __init__(self) -> None:
        self._adapters: dict = {}
        self._versions: dict = {}   # provider_id -> {external_id: version}
        self._synced_at: dict = {}  # provider_id -> last sync epoch seconds
        self._tombstones: dict = {}  # provider_id -> {external_id: True}

    def register(self, adapter: SourceAdapter) -> None:
        contract_check(adapter)
        if adapter.provider_id in self._adapters:
            raise ContractViolation(
                f"duplicate provider_id: {adapter.provider_id}")
        self._adapters[adapter.provider_id] = adapter

    def unregister(self, provider_id: str) -> None:
        self._adapters.pop(provider_id, None)

    def get(self, source_id: str) -> SourceAdapter:
        try:
            return self._adapters[source_id]
        except KeyError:
            raise UnsupportedSourceError(
                f"no adapter for source {source_id!r}; failing private "
                f"(known: {sorted(self._adapters)})")

    def provider_ids(self) -> tuple:
        return tuple(sorted(self._adapters))

    # -- sync / freshness / deletion (blueprint §3 + pipeline B step 10) ----
    def mark_synced(self, provider_id: str, records, now: float) -> None:
        """Record versions seen in a sync; sets the freshness baseline."""
        self._versions[provider_id] = {r.external_id: r.version
                                       for r in records}
        self._synced_at[provider_id] = now
        self._tombstones.setdefault(provider_id, {})

    def is_fresh(self, provider_id: str, now: float) -> bool:
        """False when never synced or the adapter's TTL has elapsed."""
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            raise UnsupportedSourceError(provider_id)
        synced = self._synced_at.get(provider_id)
        if synced is None:
            return False
        return (now - synced) <= adapter.freshness_ttl_s

    def note_deletion(self, provider_id: str, external_id: str) -> str:
        """Apply the adapter's deletion semantics. Returns what happened.

        tombstone -> keep a marker (plans referencing the version fail
        closed); purge -> drop all trace; provider_managed -> record the
        report and let the provider own it.
        """
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            raise UnsupportedSourceError(provider_id)
        sem = adapter.deletion_semantics
        if sem == "tombstone":
            self._tombstones.setdefault(provider_id, {})[external_id] = True
            return "tombstoned"
        if sem == "purge":
            self._versions.get(provider_id, {}).pop(external_id, None)
            self._tombstones.get(provider_id, {}).pop(external_id, None)
            return "purged"
        return "provider_managed"

    def is_deleted(self, provider_id: str, external_id: str) -> bool:
        if self._tombstones.get(provider_id, {}).get(external_id):
            return True
        versions = self._versions.get(provider_id, {})
        return external_id in versions and versions[external_id] is None

    def check_version(self, record: Record) -> None:
        """Fail closed when a plan pins a stale or tombstoned version.

        Plans must regenerate before mutation (blueprint §3 calendar rule).
        """
        tombed = self._tombstones.get(record.source, {})
        if tombed.get(record.external_id):
            raise AdapterError(
                f"{record.source}:{record.external_id} was deleted "
                f"(tombstoned); regenerate the plan")
        known = self._versions.get(record.source, {}).get(record.external_id)
        if known is not None and known != record.version:
            raise AdapterError(
                f"{record.source}:{record.external_id} version {record.version} "
                f"is stale (now {known}); regenerate the plan")


def contract_check(adapter: SourceAdapter) -> None:
    """Enforce the §3 declaration. Raises ContractViolation on any gap.

    Called by the registry at import/register time — a misdeclared adapter
    fails loudly here, never as a silent label gap in production.
    """
    def need(name, cond, why):
        if not cond:
            raise ContractViolation(f"{adapter.provider_id}: {name} {why}")

    need("provider_id", isinstance(adapter.provider_id, str)
         and adapter.provider_id, "must be a non-empty string")
    need("endpoint_allowlist", isinstance(adapter.endpoint_allowlist, tuple),
         "must be a tuple (empty = fixture-only)")
    need("oauth_scopes", isinstance(adapter.oauth_scopes, tuple)
         and adapter.oauth_scopes, "must declare minimal scopes")
    need("record_schema", isinstance(adapter.record_schema, dict)
         and adapter.record_schema, "must declare field schemas")
    need("subject_kinds", isinstance(adapter.subject_kinds, tuple)
         and "owner" in adapter.subject_kinds,
         "must include 'owner'")
    need("field_labels", isinstance(adapter.field_labels, dict),
         "must be a dict")
    missing = set(adapter.record_schema) - set(adapter.field_labels)
    need("field_labels coverage", not missing,
         f"fields without labels (would leak unlabeled): {sorted(missing)}")
    need("supported_transformations",
         isinstance(adapter.supported_transformations, tuple),
         "must be a tuple of named transformations")
    need("mutation_recipients", isinstance(adapter.mutation_recipients, dict),
         "must be a dict")
    need("freshness_ttl_s",
         isinstance(adapter.freshness_ttl_s, (int, float))
         and adapter.freshness_ttl_s > 0, "must be positive seconds")
    need("deletion_semantics",
         adapter.deletion_semantics in DELETION_SEMANTICS,
         f"must be one of {sorted(DELETION_SEMANTICS)}")
    # plan_ops / mutation_impact consistency
    ops = adapter.plan_ops()
    need("plan_ops", isinstance(ops, frozenset) and ops,
         "must be a non-empty frozenset")
    for op in adapter.mutation_recipients:
        try:
            adapter.mutation_impact(op)
        except Exception as exc:  # noqa: BLE001 - contract probe
            raise ContractViolation(
                f"{adapter.provider_id}: mutation_recipients lists {op!r} "
                f"but mutation_impact fails: {exc}")
