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
    """Source-id -> adapter. Unknown sources fail private, typed and loud."""

    def __init__(self) -> None:
        self._adapters: dict = {}

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
