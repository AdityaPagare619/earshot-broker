"""Disclosure Table compiler (S1).

Compiles (item, understand-output, edges, role defaults, verified chain)
into a TableRow — the ONLY thing the hot lane reads.

The compiler APPLIES edges; it never invents them (S4's lane). It ASSERTS the
chain passed verification (defense in depth — the pipeline guarantees it, the
compiler does not trust the pipeline). Unknown persons default to depth 0.
"""
from __future__ import annotations

from typing import Dict

from .models import (
    COMPILED, GeneralizationChain, Item, SecrecyEdge, TableRow,
    UnderstandOutput,
)
from .verifier import Verdict


class CompilerError(Exception):
    """The compiler refused to produce a row."""


def _edge_depth_for(edge: SecrecyEdge) -> int:
    """Depth cap implied by an edge. hidden_from -> 0 for the target (the
    target may not hear the item at any depth); cleared_to carries an explicit
    depth encoded in the target suffix 'person:3' (documented convention);
    about/for do not cap by themselves."""
    if edge.type == "hidden_from":
        return 0
    if edge.type == "cleared_to":
        # convention: target "person:maya:2" -> depth 2; plain target -> d4
        parts = edge.target.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return int(parts[1])
        return 4
    return 4  # about/for: informational, no cap


def _target_matches(edge: SecrecyEdge, person: str, roles: Dict[str, str]) -> bool:
    """Does this edge apply to `person`? Matches person id, bare role suffix,
    or the person's role."""
    target = edge.target
    base = target.rsplit(":", 1)[0] if ":" in target and target.rsplit(":", 1)[1].isdigit() else target
    if base == person:
        return True
    if base.startswith("role:"):
        role = base[len("role:"):]
        if roles.get(person) == role:
            return True
        # bare role match: edge "role:child" applies to any person whose
        # role is child (roles map), and to the pseudo-target "role:child"
        if person == base:
            return True
    return False


class TableCompiler:
    """Compiles TableRows. Tracks per-item versions; replays rejected."""

    def __init__(self) -> None:
        self._versions: Dict[str, int] = {}

    def compile(self, item: Item, understand: UnderstandOutput,
                edges: tuple, role_defaults: Dict[str, int],
                roles: Dict[str, str],
                chain: GeneralizationChain, verdict: Verdict,
                version: int) -> TableRow:
        if item.state != COMPILED:
            raise CompilerError(
                f"refusing to compile row for item {item.id} in state {item.state}: "
                f"rows are compiled only from COMPILED items"
            )
        if not verdict.passed:
            raise CompilerError(
                f"refusing to compile unverified chain for {item.id}: "
                f"{verdict.failures}"
            )
        prev = self._versions.get(item.id, 0)
        if version <= prev:
            raise CompilerError(
                f"version replay for {item.id}: {version} <= {prev}"
            )

        # clearance[p] = min(edge-imposed depths, role default). Unknown -> 0.
        persons = set(role_defaults) | set(roles)
        for edge in edges:
            base = edge.target
            if base.startswith("role:"):
                persons.add(base)
            else:
                persons.add(base.rsplit(":", 1)[0] if ":" in base and base.rsplit(":", 1)[1].isdigit() else base)
        clearance: Dict[str, int] = {}
        for person in persons:
            cap = role_defaults.get(person, 0)
            for edge in edges:
                if edge.direction != "TIGHTEN":
                    # LOOSEN edges never reach the compiler unconfirmed:
                    # the confirm queue resolves them first. Defense in depth.
                    raise CompilerError(
                        f"unconfirmed LOOSEN edge for {item.id} reached compiler"
                    )
                if _target_matches(edge, person, roles):
                    cap = min(cap, _edge_depth_for(edge))
            clearance[person] = cap

        sensitivity = max(0.0, min(1.0, understand.sensitivity))

        self._versions[item.id] = version
        return TableRow(
            item_id=item.id,
            sensitivity=sensitivity,
            clearance=clearance,
            chain=chain,
            version=version,
        )
