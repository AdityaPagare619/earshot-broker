"""End-to-end pipeline tests + one counterfactual per seam + negative control.

The seams under test:
  S1 (slow lane) -> S4 (secrecy graph) -> S2 (belief/planner) -> S3 (shape).
Each counterfactual changes the secret side of the world and asserts the
room-facing bytes do not change. The negative control proves the protection
comes from the secrecy edge, not from the code path.
"""

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent))

from integration.pipeline import SealedSpeechPipeline
from packs.loader import load_pack

PACKS = _HERE.parent.parent / "packs"


def _obgyn_day(pipe):
    return pipe.ingest(
        "event",
        {"title": "OB-GYN checkup with Dr. Mehta", "time": "3:40",
         "location": "Cloudnine", "category": "doctor's appointment",
         "daypart": "afternoon", "start": "2026-10-19T15:40",
         "end": "2026-10-19T16:40"},
        source="calendar")


def _therapy_day(pipe):
    return pipe.ingest(
        "event",
        {"title": "therapy appointment with counselor",
         "time": "3:40", "location": "clinic",
         "category": "therapy session", "daypart": "afternoon",
         "start": "2026-10-19T15:40", "end": "2026-10-19T16:40"},
        source="calendar")


def _gift_day(pipe, secret=True):
    item = pipe.ingest(
        "delivery",
        {"title": "your Instax Mini 12 camera", "sender": "Amazon",
         "items": "Instax Mini 12 camera", "for_person": "maya",
         "daypart": "evening", "start": "2026-10-19T18:00",
         "end": "2026-10-19T18:00"},
        source="email")
    pipe.compile_all()
    if secret:
        # Inference runs on the COMPILED item (Disclosure Table), like the
        # real S4 — never on raw quarantined fields.
        edges = pipe.secrecy.accept(
            pipe.secrecy.infer_edges(pipe.items[item]))
        assert any(e.type == "hidden_from" and e.target == "maya" for e in edges)
    return item


class TestEndToEnd(unittest.TestCase):
    def test_alone_brief_is_open_and_full(self):
        pack = load_pack(PACKS, "en")
        pipe = SealedSpeechPipeline(pack)
        _obgyn_day(pipe)
        pipe.ingest("event",
                    {"title": "team standup", "time": "10 AM",
                     "location": "office", "daypart": "morning"},
                    source="calendar")
        pipe.compile_all()
        resp, info = pipe.brief()
        self.assertFalse(info["plan"].cover_mode)
        depths = [pi.depth for pi in info["plan"].items]
        self.assertTrue(all(d == 4 for d in depths), f"expected all d4, got {depths}")
        self.assertNotIn(pack.ui["cover_suffix"], resp.speak)

    def test_quarantine_then_compile_pipeline(self):
        pack = load_pack(PACKS, "en")
        pipe = SealedSpeechPipeline(pack)
        iid = pipe.ingest(
            "delivery",
            {"title": "your Instax Mini 12 camera", "sender": "Amazon",
             "items": "Instax Mini 12 camera", "for_person": "maya",
             "daypart": "evening"},
            source="email")
        self.assertEqual(pipe.items[iid].state, "QUARANTINED")
        pipe.compile_all()
        self.assertEqual(pipe.items[iid].state, "COMPILED")
        self.assertIn(iid, pipe.rows)

    def test_monotone_gate_rejects_loosening(self):
        pack = load_pack(PACKS, "en")
        pipe = SealedSpeechPipeline(pack)
        _gift_day(pipe)
        from integration.contracts import SecrecyEdge
        loosen = SecrecyEdge("visible_to", "maya", until=None,
                             provenance="declared", confidence=0.99,
                             direction="LOOSEN")
        accepted = pipe.secrecy.accept([loosen])
        self.assertEqual(accepted, [],
                         "unconfirmed LOOSEN must be dropped, never applied")


class TestSeamCounterfactuals(unittest.TestCase):
    """Each test changes the SECRET side and asserts the ROOM bytes hold."""

    def _mom_present_brief(self, pack_name, build):
        pack = load_pack(PACKS, pack_name)
        pipe = SealedSpeechPipeline(pack)
        build(pipe)
        pipe.compile_all()
        return pipe.brief(signals=[("mom", "declare")])

    def test_adversarial_email_identical_output(self):
        """An email about the secret gift arrives mid-day — the classic
        injection vector. Maya is in the room. The spoken briefing must be
        byte-identical to the day without it: the inference fires on the
        email just as it does on owner-created items."""
        def with_email(pipe):
            pipe.ingest("event",
                        {"title": "team standup", "time": "10 AM",
                         "location": "office", "daypart": "morning"},
                        source="calendar")
            pipe.ingest("delivery",
                        {"title": "your Instax Mini 12 has shipped",
                         "sender": "Amazon",
                         "items": "Instax Mini 12 camera",
                         "for_person": "maya", "daypart": "morning"},
                        source="email")
            pipe.compile_all()
        def without_email(pipe):
            pipe.ingest("event",
                        {"title": "team standup", "time": "10 AM",
                         "location": "office", "daypart": "morning"},
                        source="calendar")
            pipe.compile_all()
        def maya_present(build):
            pack = load_pack(PACKS, "en")
            pipe = SealedSpeechPipeline(pack)
            build(pipe)
            return pipe.brief(signals=[("maya", "declare")])
        resp_a, _ = maya_present(with_email)
        resp_b, _ = maya_present(without_email)
        self.assertEqual(resp_a.speak, resp_b.speak)

    def test_prenatal_vs_therapy_identical_host_bytes(self):
        """Two different high-sensitivity items, same sensitivity class,
        same room: the host bytes must be indistinguishable."""
        resp_a, _ = self._mom_present_brief("en", _obgyn_day)
        resp_b, _ = self._mom_present_brief("en", _therapy_day)
        self.assertEqual(resp_a.speak, resp_b.speak)

    def test_secret_vs_no_secret_day_identical_shape(self):
        """A day with a hidden gift vs a day with no gift at all.
        Maya — the person the gift is hidden from — is in the room.
        The spoken shape must be identical; the gift leaves no trace."""
        def with_gift(pipe):
            pipe.ingest("event",
                        {"title": "team standup", "time": "10 AM",
                         "location": "office", "daypart": "morning"},
                        source="calendar")
            _gift_day(pipe)
        def no_gift(pipe):
            pipe.ingest("event",
                        {"title": "team standup", "time": "10 AM",
                         "location": "office", "daypart": "morning"},
                        source="calendar")
        def maya_present(pack_name, build):
            pack = load_pack(PACKS, pack_name)
            pipe = SealedSpeechPipeline(pack)
            build(pipe)
            pipe.compile_all()
            return pipe.brief(signals=[("maya", "declare")])
        resp_a, info_a = maya_present("en", with_gift)
        resp_b, info_b = maya_present("en", no_gift)
        self.assertEqual(resp_a.speak, resp_b.speak)
        # World A withheld the gift entirely (DEFER -> phone only); world B
        # had nothing to withhold. The room cannot tell the difference.
        self.assertTrue(any(pi.action == "DEFER" for pi in info_a["plan"].items))
        self.assertFalse(any(pi.action == "DEFER" for pi in info_b["plan"].items))

    def test_counterfactual_holds_in_hindi(self):
        """The seam guarantees are language-blind: repeat the secret/no-secret
        counterfactual through the Hindi pack, with Maya in the room."""
        def with_gift(pipe):
            pipe.ingest("event",
                        {"title": "टीम स्टैंडअप", "time": "सुबह 10",
                         "location": "ऑफिस", "daypart": "morning"},
                        source="calendar")
            iid = pipe.ingest("delivery",
                        {"title": "आपका इंस्टैक्स मिनी 12 कैमरा",
                         "sender": "अमेज़न",
                         "items": "इंस्टैक्स मिनी 12 कैमरा",
                         "for_person": "maya", "daypart": "evening"},
                        source="email")
            pipe.compile_all()
            edges = pipe.secrecy.accept(
                pipe.secrecy.infer_edges(pipe.items[iid]))
            assert any(e.type == "hidden_from" and e.target == "maya" for e in edges)
        def no_gift(pipe):
            pipe.ingest("event",
                        {"title": "टीम स्टैंडअप", "time": "सुबह 10",
                         "location": "ऑफिस", "daypart": "morning"},
                        source="calendar")
        def maya_present(build):
            pack = load_pack(PACKS, "hi")
            pipe = SealedSpeechPipeline(pack)
            build(pipe)
            pipe.compile_all()
            return pipe.brief(signals=[("maya", "declare")])
        resp_a, _ = maya_present(with_gift)
        resp_b, _ = maya_present(no_gift)
        self.assertEqual(resp_a.speak, resp_b.speak)


class TestNegativeControl(unittest.TestCase):
    def test_without_edge_the_gift_is_spoken(self):
        """Negative control: if no secrecy edge is ever inferred, the gift IS
        spoken at full depth when alone. The protection comes from the edge,
        not from a code path that hides gifts."""
        pack = load_pack(PACKS, "en")
        pipe = SealedSpeechPipeline(pack)
        pipe.ingest("delivery",
                    {"title": "your Instax Mini 12 camera", "sender": "Amazon",
                     "items": "Instax Mini 12 camera", "for_person": "maya",
                     "daypart": "evening"},
                    source="email")
        pipe.compile_all()
        resp, info = pipe.brief()
        spoken = [pi for pi in info["plan"].items if pi.action == "SPEAK"]
        self.assertEqual(len(spoken), 1)
        self.assertEqual(spoken[0].depth, 4)
        self.assertIn("Instax", resp.speak)


if __name__ == "__main__":
    unittest.main()
