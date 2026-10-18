"""End-to-end walk-in scenario through the real Host path."""
import sys
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
import host as host_module

PRIVATE_MARKERS = ("prenatal", "3:30", "clinic", "checkup")
FIXED_SUFFIX = "the rest of your day is on your phone."


class WalkinTests(unittest.TestCase):
    def setUp(self):
        host_module.HOST = host_module.Host()
        self.h = host_module.HOST

    def _spoken_texts(self):
        return [it["segment"].text for it in self.h._output]

    def test_briefing_then_walkin_stops_output(self):
        self.h.fixture_mode = "strict"
        r = self.h.utter("help me organize my afternoon")
        self.assertEqual(r["tool"], "prepare_day_brief")
        time.sleep(3.2)  # let ~2 segments release
        before = len(self._spoken_texts())
        self.assertGreaterEqual(before, 1)
        res = self.h.audience_action("mom_enters")
        self.assertTrue(res["accepted"])
        self.assertTrue(self.h.arbiter.output_stopped)
        time.sleep(3.0)  # briefing worker would have released more
        # No playable segments remain after the stop.
        playable = [it["segment"] for it in self.h._output
                    if self.h.arbiter.is_segment_playable(it["segment"])]
        self.assertEqual(playable, [])
        # NOTE (honest rescope): the pre-walk-in segments were spoken while
        # the owner was ALONE (open mode) — private markers there are
        # CORRECT, not a leak. The cover-mode case is pinned separately.

    def test_cover_mode_never_speaks_private_markers(self):
        """Mom present from the start: cover mode — zero private markers on
        the speaker, fixed suffix always appended."""
        self.h.fixture_mode = "strict"
        self.h.audience_action("mom_enters")
        r = self.h.utter("help me organize my afternoon")
        self.assertEqual(r["tool"], "prepare_day_brief")
        time.sleep(3.2)
        texts = self._spoken_texts()
        self.assertGreaterEqual(len(texts), 1)
        for text in texts:
            for marker in PRIVATE_MARKERS:
                self.assertNotIn(marker, text.lower())
        # ...and the followup "next" re-plans in cover mode too.
        r2 = self.h.utter("next")
        self.assertEqual(r2["tool"], "prepare_day_brief")
        for marker in PRIVATE_MARKERS:
            self.assertNotIn(marker, r2["spoken"].lower())
        self.assertIn(FIXED_SUFFIX, r2["spoken"].lower())

    def test_strict_fixture_quiet_phone_sync(self):
        self.h.fixture_mode = "strict"
        self.h.utter("help me organize my afternoon")
        time.sleep(0.5)
        inbox = self.h._phone_inbox
        self.assertTrue(inbox)
        for item in inbox:
            self.assertFalse(item["buzz"], "strict fixture must not buzz")
            self.assertFalse(item["badge"], "strict fixture must not badge")

    def test_relaxed_fixture_permits_existence_nudge(self):
        self.h.fixture_mode = "relaxed"
        self.h.utter("help me organize my afternoon")
        time.sleep(0.5)
        inbox = self.h._phone_inbox
        self.assertTrue(any(it["buzz"] for it in inbox))
        # ...but the speaker line is constant-shape in BOTH modes now: the
        # old relaxed "One private item — sent to your phone." was a
        # UI-visible existence leak. Killed.
        self.assertEqual(self.h.get_status()["stopped_line"].lower(),
                         "paused — moved to your phone.")

    def test_guest_probe_resists(self):
        # Probes NEVER reach a data path: one constant sentence, whatever
        # the room, whatever exists. (The old audience-dependent denial was
        # itself a probe oracle.)
        for audience in ("mom_enters", "mom_leaves"):
            self.h.audience_action(audience)
            r = self.h.utter("what was Priya's private item")
            self.assertIsNone(r["tool"])
            self.assertEqual(r["spoken"],
                             "I'll put anything about that on your phone.")
        r = self.h.utter("do I have any secrets today")
        self.assertEqual(r["spoken"],
                         "I'll put anything about that on your phone.")

    def test_resolve_day_change_keeps_private_off_speaker(self):
        self.h.fixture_mode = "strict"
        self.h.utter("help me organize my afternoon")
        r = self.h.utter("make room for a twenty-minute call")
        self.assertEqual(r["tool"], "resolve_day_change")
        for marker in PRIVATE_MARKERS:
            self.assertNotIn(marker, r["spoken"].lower())

    def test_withdraw_acknowledges_honestly(self):
        self.h.utter("help me organize my afternoon")
        r = self.h.utter("stop")
        self.assertEqual(r["tool"], "withdraw_request")
        self.assertIn("can't be unsent", r["spoken"])

    def test_next_continues_chunked_brief(self):
        """The honest mid-conversation collapse at the UI level: 'next'
        re-plans remaining items against fresh belief."""
        self.h.utter("help me organize my afternoon")
        r = self.h.utter("next")
        self.assertEqual(r["tool"], "prepare_day_brief")
        self.assertIn(FIXED_SUFFIX, r["spoken"].lower())

    def test_status_reports_honest_backend(self):
        s = self.h.get_status()
        self.assertEqual(s["backend"], "kernel_direct")
        self.assertIsNone(s["degraded"])
        self.assertIn("epoch", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
