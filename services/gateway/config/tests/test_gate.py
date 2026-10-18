"""Tests for gate.py — fail-closed enforcement at the release boundary."""
import unittest

from ..gate import ProfileGate, ProfileViolation, SecurityEvent
from ..profiles import PROFILES


class TestProfileGateA(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.gate = ProfileGate(PROFILES["public_persistent_host"],
                                on_event=self.events.append)

    def test_lease_issuance_denied_in_profile_a(self):
        with self.assertRaises(ProfileViolation):
            self.gate.check("issue_lease", tenant="t1")

    def test_private_reveal_denied_everywhere(self):
        with self.assertRaises(ProfileViolation):
            self.gate.check("reveal_private_via_mcp", tenant="t1")

    def test_public_projection_allowed(self):
        self.gate.check("public_projection", tenant="t1")  # must not raise

    def test_accept_private_task_allowed(self):
        self.gate.check("accept_private_task", tenant="t1")  # must not raise

    def test_unknown_operation_denied_fail_closed(self):
        with self.assertRaises(ProfileViolation):
            self.gate.check("delete_everything", tenant="t1")

    def test_allowed_probe_matches_check(self):
        self.assertFalse(self.gate.allowed("issue_lease"))
        self.assertTrue(self.gate.allowed("public_projection"))
        self.assertFalse(self.gate.allowed("no_such_op"))

    def test_denied_attempt_emits_security_event(self):
        try:
            self.gate.check("issue_lease", tenant="t1")
        except ProfileViolation:
            pass
        self.assertEqual(len(self.events), 1)
        ev = self.events[0]
        self.assertIsInstance(ev, SecurityEvent)
        self.assertEqual(ev.operation, "issue_lease")
        self.assertEqual(ev.profile, "public_persistent_host")
        self.assertEqual(ev.tenant, "t1")
        self.assertFalse(ev.allowed)

    def test_security_event_is_content_free(self):
        fields = set(SecurityEvent.__dataclass_fields__)
        self.assertEqual(fields, {"operation", "profile", "tenant", "allowed"})


class TestProfileGateB(unittest.TestCase):
    def setUp(self):
        self.gate = ProfileGate(PROFILES["controlled_host_demo"])

    def test_lease_issuance_allowed_in_profile_b(self):
        self.gate.check("issue_lease", tenant="t1")  # must not raise

    def test_audience_scoped_release_allowed_in_profile_b(self):
        self.gate.check("audience_scoped_release", tenant="t1")

    def test_unauthenticated_personal_api_denied(self):
        with self.assertRaises(ProfileViolation):
            self.gate.check("personal_api_unauthenticated", tenant="t1")

    def test_private_reveal_still_denied_in_profile_b(self):
        with self.assertRaises(ProfileViolation):
            self.gate.check("reveal_private_via_mcp", tenant="t1")


if __name__ == "__main__":
    unittest.main()
