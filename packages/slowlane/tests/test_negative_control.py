"""Negative controls (S1).

A privacy test that can't fail is theater (J7's rule). These controls prove
the suite detects real leaks instead of vacuously passing:

1. Counterfactual non-vacuity: if the adversarial email's content IS exposed
   in a compiled row (simulating a broken quarantine), the projection MUST
   differ from the clean world. If it didn't, the counterfactual test would
   be incapable of catching the leak it claims to guard.
2. Leaky-renderer containment: a renderer backend that drafts a chain with
   the sensitive entity at d2 must never reach the compiler — the pipeline
   falls back to boring templates, and the compiled row is clean.
"""
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent))

from slowlane import compiler, pipeline, quarantine, seam  # noqa: E402
from slowlane.models import (  # noqa: E402
    COMPILED, DraftChain, GeneralizationChain, RenderInput, TableRow,
)
from slowlane.render import RenderBackend  # noqa: E402
from slowlane.understand import fixture_lexicon  # noqa: E402
try:
    from .test_counterfactual import (  # noqa: E402; discover mode
        ROLE_DEFAULTS, ROLES, LEXICON, _compile_event,
    )
except ImportError:  # noqa: E402; run-from-directory mode
    from test_counterfactual import (
        ROLE_DEFAULTS, ROLES, LEXICON, _compile_event,
    )


class LeakyRenderer(RenderBackend):
    """Test double: a "model" that drafts a chain leaking the entity at d2."""

    @property
    def name(self):
        return "leaky-test-double"

    def draft_chain(self, render_input):
        depths = (
            "OB-GYN checkup with Dr. Mehta at 3:40 at Cloudnine",  # d4
            "doctor's appointment at 3:40",                          # d3
            "appointment at Cloudnine at 3:40",                     # d2 LEAK
            "something this afternoon",                             # d1
        )
        return DraftChain(depths=depths, renditions={"en": depths},
                          backend="leaky-test-double")


class NegativeControlTest(unittest.TestCase):
    def test_broken_quarantine_is_detected(self):
        # Clean world.
        store_a, comp_a = quarantine.QuarantineStore(), compiler.TableCompiler()
        row_a = _compile_event(store_a, comp_a)
        proj_a = seam.projection_bytes(seam.project_for_hotlane(
            {row_a.item_id: row_a},
            {row_a.item_id: store_a.get(row_a.item_id).state}))

        # Broken world: the email's content leaked into a "compiled" row
        # (quarantine bypassed, verifier bypassed — the nightmare scenario).
        leaky_chain = GeneralizationChain(
            depths=("x", "x", "wire $5000 to account 12345", "something"),
            renditions={"en": ("x", "x", "wire $5000 to account 12345",
                               "something")},
        )
        leaky_row = TableRow(item_id="email_666", sensitivity=1.0,
                             clearance={"priya": 4}, chain=leaky_chain,
                             version=1)
        proj_b = seam.projection_bytes(seam.project_for_hotlane(
            {row_a.item_id: row_a, "email_666": leaky_row},
            {row_a.item_id: COMPILED, "email_666": COMPILED}))

        self.assertNotEqual(proj_a, proj_b,
                            "NEGATIVE CONTROL FAILED: the counterfactual "
                            "harness cannot detect an actual leak")
        self.assertIn(b"account 12345", proj_b)

    def test_leaky_renderer_contained_by_fallback(self):
        store, comp = quarantine.QuarantineStore(), compiler.TableCompiler()
        store.ingest("evt_9", "priya", "event", "gcal",
                     start="2026-10-21T15:40+05:30",
                     end="2026-10-21T16:00+05:30")
        ri = RenderInput(item_id="evt_9", kind="event", time_label="3:40 PM",
                         daypart="afternoon", location_type="clinic",
                         counterparty_role="doctor", langs=("en",))
        result = pipeline.process_item(
            store, comp, "evt_9",
            "OB-GYN checkup with Dr. Mehta at 3:40 at Cloudnine",
            ri, (), ROLE_DEFAULTS, ROLES, LEXICON, version=1,
            renderer=LeakyRenderer(),
            quasi=("afternoon", "tuesday", "clinic"),
        )
        # The leaky draft never reached the compiler: fallback engaged.
        self.assertTrue(result.ok, result.verify_failures)
        self.assertIn("template-fallback", result.backend_used)
        self.assertEqual(result.attempts, 2)
        for depth_text in result.row.chain.depths:
            self.assertNotIn("Cloudnine", depth_text)


if __name__ == "__main__":
    unittest.main()
