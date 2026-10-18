"""Tests for readiness.py — gates as checkable code."""
import unittest

from ..profiles import PROFILES
from ..readiness import READINESS_GATES, deploy_blocked, run_readiness


class TestReadiness(unittest.TestCase):
    def test_all_eleven_blueprint_gates_present(self):
        names = [g.name for g in READINESS_GATES]
        self.assertEqual(len(names), 11)
        self.assertIn("auth_implemented_and_reviewed", names)
        self.assertIn("cross_tenant_tests", names)
        self.assertIn("certification_questions_resolved", names)

    def test_automated_gates_pass_against_real_kernel(self):
        results = {r.name: r for r in run_readiness()}
        for name in ("cross_tenant_tests",
                     "private_data_absent_from_observability",
                     "common_release_assembler",
                     "secret_dependent_errors_contained",
                     "supported_transformations_tested"):
            self.assertEqual(results[name].status, "PASS", name)

    def test_manual_gates_block_without_signoff(self):
        blocked = deploy_blocked(run_readiness())
        # 6 MANUAL gates, none signed -> all block
        self.assertIn("auth_implemented_and_reviewed", blocked)
        self.assertIn("certification_questions_resolved", blocked)
        self.assertIn("renderer_sensor_claims_measured", blocked)
        self.assertEqual(len(blocked), 6)

    def test_signed_manual_gate_does_not_block(self):
        signoffs = {
            "auth_implemented_and_reviewed": {
                "signed_by": "security-reviewer",
                "date": "2026-10-18",
                "evidence_ref": "evidence/auth-review.md",
            }
        }
        blocked = deploy_blocked(run_readiness(signoffs))
        self.assertNotIn("auth_implemented_and_reviewed", blocked)
        self.assertEqual(len(blocked), 5)

    def test_incomplete_signoff_still_blocks(self):
        signoffs = {"auth_implemented_and_reviewed": {"signed_by": "x"}}
        blocked = deploy_blocked(run_readiness(signoffs))
        self.assertIn("auth_implemented_and_reviewed", blocked)

    def test_gate_result_evidence_is_nonempty(self):
        for r in run_readiness():
            self.assertTrue(r.evidence, r.name)


if __name__ == "__main__":
    unittest.main()
