"""Source adapters: the executable §3 contract (dossier §8.4, blueprint §3)."""
from .contract import (AdapterRegistry, ContractViolation, Record,
                       MutationImpact, RecurrenceError, SourceAdapter,
                       UnsupportedSourceError, contract_check)
from .calendar_adapter import FixtureCalendarAdapter
from .tasks_adapter import FixtureTasksAdapter

__all__ = [
    "AdapterRegistry", "ContractViolation", "FixtureCalendarAdapter",
    "FixtureTasksAdapter",
    "MutationImpact", "Record", "RecurrenceError", "SourceAdapter",
    "UnsupportedSourceError", "contract_check",
]


def default_registry() -> AdapterRegistry:
    reg = AdapterRegistry()
    reg.register(FixtureCalendarAdapter())
    reg.register(FixtureTasksAdapter())
    return reg
