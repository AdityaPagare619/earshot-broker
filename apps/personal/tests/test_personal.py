"""J5 personal surface tests — run with: python3 -m unittest test_personal -v
Run from apps/personal/ so the personal package + kernel resolve.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from personal import auth, preview as preview_mod, profile as profile_mod  # noqa: E402
from personal.fixture_calendar import FixtureCalendar, contract  # noqa: E402
from personal.inbox import PersonalSurface  # noqa: E402


def make_surface(directory: str) -> tuple[PersonalSurface, str, dict]:
    profile, _log = profile_mod.run_onboarding(directory)
    token = auth.mint_session(profile)
    profile_mod.save_profile(profile, directory)
    surface = PersonalSurface(profile, directory)
    return surface, token, profile


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_seven_steps_logged_and_profile_v1(self):
        profile, log = profile_mod.run_onboarding(self.dir)
        self.assertEqual(profile["profile_version"], 1)
        self.assertEqual(len(log), 7 + 5 - 1)  # 7 steps; step 4 logs 5 field lines
        steps = [line.split(".")[0] for line in log]
        self.assertEqual(steps[:3], ["1", "2", "3"])

    def test_private_by_default_and_separate_declassification(self):
        profile, _ = profile_mod.run_onboarding(self.dir)
        self.assertEqual(profile["defaults"]["new_data"], "private")
        decl = profile["declassify"]
        self.assertEqual(set(decl), {"existence", "busy_times", "leave_by", "reminders", "sounds"})
        self.assertFalse(decl["existence"])
        self.assertTrue(decl["busy_times"])

    def test_non_fixture_source_refused(self):
        with self.assertRaises(ValueError):
            profile_mod.run_onboarding(self.dir, defaults={"source_uri": "https://evil.example/cal"})

    def test_adapter_contract_declares_private_defaults(self):
        c = contract()
        self.assertTrue(c["private_defaults"])
        self.assertTrue(c["fixture"])
        self.assertIn("read:busy", c["scopes"])


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.surface, self.token, self.profile = make_surface(self.dir)
        self.brief = self.surface.prepare_day_brief(self.token)
        self.ref = self.brief["request_ref"]

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_listings_expose_no_private_content(self):
        listing = json.dumps(self.surface.list_requests(self.token))
        self.assertNotIn("Prenatal", listing)
        self.assertNotIn("Clinic", listing)

    def test_open_requires_valid_session(self):
        with self.assertRaises(PermissionError):
            self.surface.open_request("bogus-token", self.ref)

    def test_open_returns_exact_plan_and_labeled_facts(self):
        facts, plan = self.surface.open_request(self.token, self.ref)
        values = [f.value for f in facts]
        self.assertTrue(any("Prenatal" in v for v in values))
        self.assertIn("proposed_call", plan)
        self.assertEqual(plan["planner"], "fixture-deterministic (NOT the dossier AI planner)")

    def test_wrong_owner_cannot_open(self):
        evil = dict(self.profile)
        evil["session"] = {"token": self.token, "owner": "mallory",
                           "tenant": "house-a", "minted_at": time.time()}
        evil_surface = PersonalSurface(evil, self.dir)
        with self.assertRaises(PermissionError):
            evil_surface.open_request(self.token, self.ref)

    def test_approve_binds_digest_and_detects_tamper(self):
        result = self.surface.approve(self.token, self.ref)
        self.assertTrue(self.surface.approval_valid(self.token, self.ref))
        self.assertEqual(len(result["approved_plan_digest"]), 64)
        # Tamper with the stored plan: the old approval must not validate.
        self.surface.store._plans[self.ref]["proposed_call"] = {"slot_start": "forged"}
        self.assertFalse(self.surface.approval_valid(self.token, self.ref))


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.surface, self.token, self.profile = make_surface(self.dir)
        self.ref = self.surface.prepare_day_brief(self.token)["request_ref"]

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_public_projection_excludes_private(self):
        data = preview_mod.preview(self.surface, self.token, self.ref)
        public = " ".join(data["public"])
        self.assertNotIn("Prenatal", public)
        self.assertIn("Team lunch", public)

    def test_uncontrolled_host_matches_public(self):
        data = preview_mod.preview(self.surface, self.token, self.ref)
        self.assertEqual(data["room_uncontrolled_host"], data["public"])

    def test_room_assumed_lists_assumptions(self):
        data = preview_mod.preview(self.surface, self.token, self.ref)
        self.assertTrue(any("alone" in a or "assumption" in a for a in data["assumptions"]))
        self.assertGreaterEqual(len(data["assumptions"]), 3)

    def test_counterfactual_public_projection_stable(self):
        result = preview_mod.prove(self.surface, self.token, self.ref)
        self.assertTrue(result["counterfactual_ok"])
        self.assertEqual(set(result["variants"]), {"therapy", "removed"})
        for variant in result["variants"].values():
            self.assertTrue(variant["identical_to_baseline"])

    def test_counterfactual_variant_actually_changed_private_content(self):
        # Guard against a vacuous test: the variants must differ privately.
        cal = FixtureCalendar(self.profile["sources"][0]["uri"])
        swapped = cal.with_title_swapped("evt-1", "Therapy session — Downtown")
        titles = [e["title"] for e in swapped.events()]
        self.assertIn("Therapy session — Downtown", titles)
        removed = cal.with_title_swapped("evt-1", None)
        self.assertEqual(len(removed.events()), len(cal.events()) - 1)


    def test_receipt_prefix_resolution(self):
        prefix = self.ref[:8]
        facts, _plan = self.surface.open_request(self.token, prefix)
        self.assertTrue(any("Prenatal" in f.value for f in facts))
        with self.assertRaises(PermissionError):
            self.surface.open_request(self.token, "deadbeef")


class QuickstartTests(unittest.TestCase):
    def test_end_to_end_within_budget(self):
        directory = tempfile.mkdtemp()
        try:
            sys.argv = ["quickstart", "--dir", directory, "--html", "p.html"]
            t0 = time.time()
            import runpy
            try:
                runpy.run_path(
                    str(_HERE.parent / "quickstart.py"),
                    run_name="__main__")
                code = 0
            except SystemExit as e:
                code = e.code
            elapsed = time.time() - t0
            self.assertEqual(code, 0, "quickstart exited non-zero")
            self.assertLess(elapsed, 90, f"quickstart took {elapsed:.1f}s")
            self.assertTrue((Path(directory) / "p.html").exists())
            self.assertTrue((Path(directory) / ".earshot-profile.json").exists())
        finally:
            shutil.rmtree(directory)


if __name__ == "__main__":
    unittest.main()
