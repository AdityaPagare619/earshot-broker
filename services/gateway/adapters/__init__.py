"""Source adapters: the executable §3 contract (dossier §8.4, blueprint §3)."""
from .contract import (AdapterRegistry, ContractViolation, Record,
                       MutationImpact, RecurrenceError, SourceAdapter,
                       UnsupportedSourceError, contract_check)
from .calendar_adapter import FixtureCalendarAdapter

__all__ = [
    "AdapterRegistry", "ContractViolation", "FixtureCalendarAdapter",
    "MutationImpact", "Record", "RecurrenceError", "SourceAdapter",
    "UnsupportedSourceError", "contract_check",
]


def default_registry() -> AdapterRegistry:
    reg = AdapterRegistry()
    reg.register(FixtureCalendarAdapter())
    return reg
