"""Tests for profiles.py — the deployment switch itself."""
import dataclasses
import os
import tempfile
import unittest

from ..profiles import PROFILES, ProfileError, load_profile


class TestProfileLoading(unittest.TestCase):
    def test_known_profiles_load(self):
        for name in ("public_persistent_host", "controlled_host_demo"):
            cfg = load_profile({"EARSHOT_PROFILE": name})
            self.assertEqual(cfg.name, name)

    def test_missing_env_fails_closed(self):
        with self.assertRaises(ProfileError):
            load_profile({})

    def test_empty_env_fails_closed(self):
        with self.assertRaises(ProfileError):
            load_profile({"EARSHOT_PROFILE": "   "})

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(ProfileError):
            load_profile({"EARSHOT_PROFILE": "prod_superuser"})

    def test_config_is_frozen(self):
        cfg = load_profile({"EARSHOT_PROFILE": "public_persistent_host"})
        with self.assertRaises(dataclasses.FrozenInstanceError):
            cfg.allow_lease_issuance = True  # type: ignore[misc]

    def test_profile_a_matches_blueprint_section_10(self):
        p = PROFILES["public_persistent_host"]
        self.assertFalse(p.audience_sensitive_content_to_mcp)
        self.assertFalse(p.private_reveal_via_mcp)
        self.assertEqual(p.public_result_status, "permission-dependent")
        self.assertEqual(p.personal_api, "independently_authenticated")
        self.assertFalse(p.allow_lease_issuance)
        self.assertFalse(p.local_arbiter_required)

    def test_profile_b_matches_blueprint_section_10(self):
        p = PROFILES["controlled_host_demo"]
        self.assertTrue(p.allow_lease_issuance)
        self.assertTrue(p.local_arbiter_required)
        self.assertTrue(p.sensor_heartbeat_required)
        self.assertTrue(p.fresh_context_after_epoch_change)
        self.assertFalse(p.autoplay_after_retrust)
        # Even in the demo profile, raw private never crosses MCP.
        self.assertFalse(p.private_reveal_via_mcp)

    def test_toml_tunable_override(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as fh:
            fh.write("[tuning]\nlease_ttl_seconds = 0.5\n")
            path = fh.name
        try:
            cfg = load_profile({"EARSHOT_PROFILE": "controlled_host_demo",
                                "EARSHOT_CONFIG_FILE": path})
            self.assertEqual(cfg.lease_ttl_seconds, 0.5)
            # capability flags untouched by tuning
            self.assertTrue(cfg.allow_lease_issuance)
        finally:
            os.unlink(path)

    def test_toml_capability_override_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as fh:
            fh.write("[tuning]\nallow_lease_issuance = true\n")
            path = fh.name
        try:
            with self.assertRaises(ProfileError):
                load_profile({"EARSHOT_PROFILE": "public_persistent_host",
                              "EARSHOT_CONFIG_FILE": path})
        finally:
            os.unlink(path)

    def test_toml_garbage_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as fh:
            fh.write("this is [ not toml\n")
            path = fh.name
        try:
            with self.assertRaises(ProfileError):
                load_profile({"EARSHOT_PROFILE": "public_persistent_host",
                              "EARSHOT_CONFIG_FILE": path})
        finally:
            os.unlink(path)

    def test_toml_negative_tunable_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as fh:
            fh.write("[tuning]\nreceipt_ttl_seconds = -5\n")
            path = fh.name
        try:
            with self.assertRaises(ProfileError):
                load_profile({"EARSHOT_PROFILE": "public_persistent_host",
                              "EARSHOT_CONFIG_FILE": path})
        finally:
            os.unlink(path)

    def test_describe_is_content_free(self):
        desc = PROFILES["public_persistent_host"].describe()
        blob = str(desc).lower()
        for word in ("secret", "fact", "value", "title", "topic"):
            self.assertNotIn(word, blob)


if __name__ == "__main__":
    unittest.main()
