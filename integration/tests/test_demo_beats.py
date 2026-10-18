"""Beat property tests: each of the 5 demo beats asserts its core property.

These are the machine-checkable version of the demo's narration — if a beat
can't be asserted, it gets cut (K2), not faked.
"""
import os
import unittest


from earshot.demo import five_beats as demo
from earshot.integration.pipeline import SealedSpeechPipeline
from earshot.packs.loader import load_pack

PACKS = os.path.join(os.path.dirname(__file__), "..", "..", "packs")


class TestDemoBeats(unittest.TestCase):
    def test_beat1_alone_open_mode(self):
        """Alone: open mode, everything at d4, no cover suffix."""
        pack = load_pack(PACKS, "en")
        pipe, resp, info = demo.build_day(pack, "en")
        self.assertFalse(info["plan"].cover_mode)
        self.assertTrue(all(pi.depth == 4 for pi in info["plan"].items))
        self.assertNotIn(pack.ui["cover_suffix"], resp.speak)

    def test_beat2_gift_inferred_hidden(self):
        """The gift email is quarantined on ingest; the secrecy fixture
        infers hidden_from(maya) at 0.91 without any human-written rule."""
        pack = load_pack(PACKS, "en")
        pipe = SealedSpeechPipeline(pack)
        iid = pipe.ingest("delivery", demo.STRINGS["en"]["gift"], source="email")
        self.assertEqual(pipe.items[iid].state, "QUARANTINED")
        pipe.compile_all()
        edges = pipe.secrecy.accept(
            pipe.secrecy.infer_edges(pipe.items[iid]))
        hidden = [e for e in edges
                  if e.type == "hidden_from" and e.target == "maya"]
        self.assertEqual(len(hidden), 1)
        self.assertGreaterEqual(hidden[0].confidence, 0.6)

    def test_beat3_mom_cover_mode(self):
        """Mom arrives: cover mode, OB-GYN at d3, fixed suffix present."""
        pack = load_pack(PACKS, "en")
        pipe, resp, info = demo.build_day(pack, "en")
        resp3, info3 = pipe.brief(signals=[("mom", "declare")])
        self.assertTrue(info3["plan"].cover_mode)
        depths = {pipe.items[pi.item_id].fields["title"]: pi.depth
                  for pi in info3["plan"].items}
        self.assertEqual(depths["OB-GYN checkup with Dr. Mehta"], 3)
        self.assertTrue(resp3.speak.endswith(pack.ui["cover_suffix"]))

    def test_beat4_counterfactual_identical(self):
        """Therapy day vs no-therapy day, mom present: byte-identical speak."""
        pack = load_pack(PACKS, "en")
        _, resp_a, _ = demo.build_day(pack, "en", with_therapy=True,
                                      mom_present=True)
        _, resp_b, _ = demo.build_day(pack, "en", with_therapy=False,
                                      mom_present=True)
        self.assertEqual(resp_a.speak, resp_b.speak)

    def test_beat5_probe_constant_and_walkin_boundary(self):
        """Probe answer identical with/without the gift; the walk-in
        collapse happens at the turn boundary, never mid-turn."""
        pack = load_pack(PACKS, "en")
        pipe, resp, info = demo.build_day(pack, "en")
        probe = pipe.ask_about(demo.STRINGS["en"]["probe"])
        pipe_nogift = SealedSpeechPipeline(pack)
        pipe_nogift.ingest("event", demo.STRINGS["en"]["standup"],
                           source="calendar")
        pipe_nogift.compile_all()
        probe2 = pipe_nogift.ask_about(demo.STRINGS["en"]["probe"])
        self.assertEqual(probe.speak, probe2.speak)
        self.assertEqual(probe.speak, pack.ui["probe_response"])

        # Walk-in: turn 1 alone (full detail), guest joins, turn 2 re-plans.
        pipe_walk, _, info_w1 = demo.build_day(pack, "en")
        c1 = pipe_walk.shape.chunk(info_w1["plan"], n=2)
        r1 = pipe_walk.shape.assemble(c1[0], pipe_walk.rows, pack,
                                      pipe_walk.fields)
        resp_t2, info_w2 = pipe_walk.brief(signals=[("unknown", "guest")])
        c2 = pipe_walk.shape.chunk(info_w2["plan"], n=2)
        r2 = pipe_walk.shape.assemble(c2[0], pipe_walk.rows, pack,
                                      pipe_walk.fields)
        self.assertNotEqual(r1.speak, r2.speak)
        self.assertTrue(info_w2["plan"].cover_mode)

    def test_beats_hold_in_hindi(self):
        """Beats 1, 3, and 4 hold through the Hindi pack unchanged."""
        pack = load_pack(PACKS, "hi")
        pipe, resp, info = demo.build_day(pack, "hi")
        self.assertFalse(info["plan"].cover_mode)
        resp3, info3 = pipe.brief(signals=[("mom", "declare")])
        self.assertTrue(info3["plan"].cover_mode)
        self.assertTrue(resp3.speak.endswith(pack.ui["cover_suffix"]))
        _, resp_a, _ = demo.build_day(pack, "hi", with_therapy=True,
                                      mom_present=True)
        _, resp_b, _ = demo.build_day(pack, "hi", with_therapy=False,
                                      mom_present=True)
        self.assertEqual(resp_a.speak, resp_b.speak)


if __name__ == "__main__":
    unittest.main()
