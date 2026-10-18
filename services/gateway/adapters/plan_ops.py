"""Plan-operator validation — the integration seam for the gateway server.

Blueprint §4: a validator rejects unknown operators and source IDs not
supplied by the server. Each adapter declares the ops it serves via
``plan_ops()``; this module checks a plan's op list against the registry.

Ownership: the full plan-AST validator is J3's area (services/gateway/mcp/);
this is the adapter-side descriptor check they can import. Flagged in the
J9 report.
"""
from __future__ import annotations

from .contract import AdapterError, AdapterRegistry


class UnknownPlanOp(AdapterError):
    """A plan references an operator no registered adapter serves."""


class AmbiguousPlanOp(AdapterError):
    """Two adapters claim the same operator — the plan must name its source."""


def validate_plan_ops(registry: AdapterRegistry,
                      ops: list) -> dict:
    """Map each op -> provider_id serving it. Raises on unknown/ambiguous.

    ``ops`` are bare operator names (e.g. "load_busy_intervals"). Plans that
    carry explicit source bindings should resolve them before calling this;
    this is the last line of defense, not the first.
    """
    owners: dict = {}
    for op in ops:
        serving = [pid for pid in registry.provider_ids()
                   if op in registry.get(pid).plan_ops()]
        if not serving:
            raise UnknownPlanOp(
                f"no registered adapter serves plan op {op!r}; "
                f"known ops: {sorted(known_ops(registry))}")
        if len(serving) > 1:
            raise AmbiguousPlanOp(
                f"plan op {op!r} claimed by {serving}; bind an explicit source")
        owners[op] = serving[0]
    return owners


def known_ops(registry: AdapterRegistry) -> frozenset:
    ops = set()
    for pid in registry.provider_ids():
        ops |= set(registry.get(pid).plan_ops())
    return frozenset(ops)
