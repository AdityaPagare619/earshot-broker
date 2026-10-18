"""End-to-end walk-in scenario through the real Host path."""
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import host as host_module

PRIVATE_MARKERS = ("prenatal", "15:40", "clinic", "appointment")


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
        # Strict fixture: nothing private ever reached the speaker.
        for text in self._spoken_texts():
            for marker in PRIVATE_MARKERS:
                self.assertNotIn(marker, text.lower())

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
        self.assertIn("private item", self.h.get_status()["stopped_line"].lower())

    def test_guest_probe_denied_generically(self):
        self.h.audience_action("mom_enters")
        r = self.h.utter("what was Priya's private item")
        self.assertIsNone(r["tool"])
        self.assertNotIn("prenatal", r["spoken"].lower())
        self.assertIn("can't help", r["spoken"].lower())

    def test_resolve_day_change_keeps_private_off_speaker(self):
        self.h.fixture_mode = "strict"
        r = self.h.utter("make room for a twenty-minute call")
        self.assertEqual(r["tool"], "resolve_day_change")
        for marker in PRIVATE_MARKERS:
            self.assertNotIn(marker, r["spoken"].lower())

    def test_withdraw_acknowledges_honestly(self):
        r = self.h.utter("stop")
        self.assertEqual(r["tool"], "withdraw_request")
        self.assertIn("can't be unsent", r["spoken"])

    def test_status_reports_honest_backend(self):
        s = self.h.get_status()
        self.assertEqual(s["backend"], "kernel_direct")
        self.assertIsNone(s["degraded"])
        self.assertIn("epoch", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
