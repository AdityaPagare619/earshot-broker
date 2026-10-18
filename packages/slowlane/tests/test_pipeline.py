"""Tests: Stage 1 pipeline end-to-end (fixture backends).

process_item: ingest (QUARANTINED) -> understand -> render -> verify ->
compile -> TableRow. Failures leave the item QUARANTINED (fail private).
"""
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))

from earshot.slowlane import compiler, pipeline, quarantine  # noqa: E402
from earshot.slowlane.models import COMPILED, QUARANTINED, RenderInput, SecrecyEdge  # noqa: E402
from earshot.slowlane.understand import fixture_lexicon  # noqa: E402

ROLE_DEFAULTS = {"priya": 4, "rahul": 4, "mom": 2, "role:child": 1, "role:guest": 0}
ROLES = {"priya": "owner", "rahul": "partner", "mom": "guest", "maya": "child"}

LEXICON = fixture_lexicon()


def _run(kind="event", text_hint="", item_id="itm_1", **kw):
    store = quarantine.QuarantineStore()
    comp = compiler.TableCompiler()
    store.ingest(item_id, "priya", kind, "gcal",
                 start="2026-10-21T15:40+05:30", end="2026-10-21T16:00+05:30")
    render_input = RenderInput(
        item_id=item_id, kind=kind, time_label="3:40 PM",
        daypart="afternoon", location_type="clinic" if kind == "event" else "home",
        counterparty_role="doctor" if kind == "event" else "",
        langs=("en",),
    )
    edges = kw.get("edges", ())
    return pipeline.process_item(
        store, comp, item_id, text_hint, render_input, edges,
        ROLE_DEFAULTS, ROLES, LEXICON, version=1,
        quasi=("afternoon", "tuesday", "clinic"),
    ), store


class PipelineTest(unittest.TestCase):
    def test_event_compiles(self):
        result, store = _run(
            kind="event",
            text_hint="OB-GYN checkup with Dr. Mehta at 3:40 at Cloudnine",
        )
        self.assertTrue(result.ok, result.verify_failures)
        self.assertIsNotNone(result.row)
        self.assertEqual(result.row.item_id, "itm_1")
        self.assertEqual(result.row.version, 1)
        self.assertEqual(store.get("itm_1").state, COMPILED)
        self.assertEqual(result.backend_used, "fixture-template")

    def test_delivery_compiles(self):
        result, store = _run(
            kind="delivery",
            text_hint="Your Instax Mini order has shipped",
            edges=(SecrecyEdge(type="hidden_from", target="maya",
                               until="2026-11-03", provenance="inferred",
                               confidence=0.91, direction="TIGHTEN"),),
        )
        self.assertTrue(result.ok, result.verify_failures)
        self.assertEqual(result.row.clearance["maya"], 0)
        self.assertAlmostEqual(result.row.sensitivity, 0.7)

    def test_unknown_content_fails_private(self):
        # No topics matched -> sensitivity 1.0, still compiles (templates are
        # generic) but maximally sensitive.
        result, _ = _run(kind="note", text_hint="xqz wobble flimflam")
        self.assertTrue(result.ok)
        self.assertEqual(result.row.sensitivity, 1.0)

    def test_row_is_the_only_hotlane_artifact(self):
        result, _ = _run(kind="event", text_hint="dentist checkup at 3:40")
        row = result.row
        # The row carries no raw content, no inference traces: the specific
        # term "dentist" appears nowhere in the compiled chain.
        for depth_text in row.chain.depths:
            self.assertNotIn("dentist", depth_text.lower())
            self.assertNotIn("vault://", depth_text)


if __name__ == "__main__":
    unittest.main()
