"""Tests: Disclosure Table compiler.

The compiler APPLIES edges; it never invents them. Unknown persons default
to depth 0. Unverified chains and version replays are refused.
"""
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent))

from slowlane.compiler import CompilerError, TableCompiler  # noqa: E402
from slowlane.models import (  # noqa: E402
    COMPILED, DraftChain, GeneralizationChain, QUARANTINED, SecrecyEdge,
    UnderstandOutput, quarantine_new, transition,
)
from slowlane.verifier import Verdict  # noqa: E402

PASS = Verdict(passed=True, failures=(), checks_run=4)
FAIL = Verdict(passed=False, failures=("entity-leak: x",), checks_run=4)

CHAIN = GeneralizationChain(
    depths=("d4", "d3", "d2", "d1"),
    renditions={"en": ("d4", "d3", "d2", "d1")},
)

UNDERSTAND = UnderstandOutput(
    item_id="itm_1", topics=("health",), entities={},
    sensitive={}, sensitive_topics={}, sensitivity=0.9,
    confidence=0.9, lang_detected=("en",),
)

ROLE_DEFAULTS = {"priya": 4, "rahul": 4, "mom": 2, "role:child": 1, "role:guest": 0}
ROLES = {"priya": "owner", "rahul": "partner", "mom": "guest", "maya": "child"}


def _edge(type_, target, direction="TIGHTEN", conf=0.9, prov="inferred"):
    return SecrecyEdge(type=type_, target=target, until=None,
                       provenance=prov, confidence=conf, direction=direction)


def _compiled_item():
    item = quarantine_new("itm_1", "priya", "event", "gcal")
    return transition(item, COMPILED)


class CompileTest(unittest.TestCase):
    def setUp(self):
        self.c = TableCompiler()

    def test_clearance_is_min_of_edges_and_defaults(self):
        edges = (_edge("hidden_from", "mom"),)
        row = self.c.compile(_compiled_item(), UNDERSTAND, edges,
                             ROLE_DEFAULTS, ROLES, CHAIN, PASS, version=1)
        self.assertEqual(row.clearance["mom"], 0)      # edge tightens below default 2
        self.assertEqual(row.clearance["priya"], 4)    # default untouched
        self.assertEqual(row.clearance["role:child"], 1)

    def test_hidden_from_role_applies_to_members(self):
        edges = (_edge("hidden_from", "role:child"),)
        row = self.c.compile(_compiled_item(), UNDERSTAND, edges,
                             ROLE_DEFAULTS, ROLES, CHAIN, PASS, version=1)
        self.assertEqual(row.clearance["maya"], 0)

    def test_unknown_person_defaults_zero(self):
        row = self.c.compile(_compiled_item(), UNDERSTAND, (),
                             ROLE_DEFAULTS, ROLES, CHAIN, PASS, version=1)
        self.assertEqual(row.clearance.get("stranger", 0), 0)

    def test_cleared_to_depth_convention(self):
        edges = (_edge("cleared_to", "mom:3"),)
        row = self.c.compile(_compiled_item(), UNDERSTAND, edges,
                             ROLE_DEFAULTS, ROLES, CHAIN, PASS, version=1)
        self.assertEqual(row.clearance["mom"], 2)  # min(default 2, edge 3)

    def test_refuses_uncompiled_item(self):
        item = quarantine_new("itm_1", "priya", "event", "gcal")  # QUARANTINED
        with self.assertRaises(CompilerError):
            self.c.compile(item, UNDERSTAND, (), ROLE_DEFAULTS, ROLES,
                           CHAIN, PASS, version=1)

    def test_refuses_unverified_chain(self):
        with self.assertRaises(CompilerError):
            self.c.compile(_compiled_item(), UNDERSTAND, (), ROLE_DEFAULTS,
                           ROLES, CHAIN, FAIL, version=1)

    def test_refuses_version_replay(self):
        item = _compiled_item()
        self.c.compile(item, UNDERSTAND, (), ROLE_DEFAULTS, ROLES,
                       CHAIN, PASS, version=2)
        with self.assertRaises(CompilerError):
            self.c.compile(item, UNDERSTAND, (), ROLE_DEFAULTS, ROLES,
                           CHAIN, PASS, version=2)
        with self.assertRaises(CompilerError):
            self.c.compile(item, UNDERSTAND, (), ROLE_DEFAULTS, ROLES,
                           CHAIN, PASS, version=1)

    def test_refuses_unconfirmed_loosen(self):
        edges = (_edge("cleared_to", "mom:4", direction="LOOSEN",
                       prov="confirmed"),)
        # Even a "confirmed" LOOSEN must not arrive here unprocessed: the
        # confirm queue resolves loosenings before the compiler sees them.
        with self.assertRaises(CompilerError):
            self.c.compile(_compiled_item(), UNDERSTAND, edges,
                           ROLE_DEFAULTS, ROLES, CHAIN, PASS, version=1)

    def test_sensitivity_clamped(self):
        u = UnderstandOutput(item_id="itm_1", topics=(), entities={},
                             sensitive={}, sensitive_topics={},
                             sensitivity=9.9, confidence=0.9,
                             lang_detected=("en",))
        row = self.c.compile(_compiled_item(), u, (), ROLE_DEFAULTS, ROLES,
                             CHAIN, PASS, version=1)
        self.assertEqual(row.sensitivity, 1.0)


if __name__ == "__main__":
    unittest.main()
