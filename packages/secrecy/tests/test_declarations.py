"""Declarations: asymmetric trust at ingest; deterministic parsing (S4)."""
import unittest

from earshot.secrecy.declarations import (DeclarationLog, classify, parse_declaration)


class TrustTableTest(unittest.TestCase):
    def test_presence_adds_never_removes(self):
        for source in ("voice", "app"):
            for auth in (False, True):
                add, remove, cap = classify("present", source, auth)
                self.assertTrue(add)
                self.assertFalse(remove)

    def test_voice_alone_capped(self):
        add, remove, cap = classify("absent", "voice", False)
        self.assertFalse(add)
        self.assertTrue(remove)
        self.assertEqual(cap, 0.7)

    def test_authenticated_app_alone_uncapped(self):
        add, remove, cap = classify("absent", "app", True)
        self.assertFalse(add)
        self.assertTrue(remove)
        self.assertIsNone(cap)

    def test_unauthenticated_app_alone_capped_like_voice(self):
        add, remove, cap = classify("absent", "app", False)
        self.assertEqual(cap, 0.7)


class DeclarationLogTest(unittest.TestCase):
    def test_declare_tags_trust_class(self):
        log = DeclarationLog()
        d = log.declare("mom", "present", source="voice")
        self.assertTrue(d.can_add)
        self.assertFalse(d.can_remove)
        d2 = log.declare("owner", "absent", source="voice")
        self.assertTrue(d2.can_remove)
        self.assertEqual(d2.max_loosen_sensitivity, 0.7)

    def test_log_is_append_only(self):
        log = DeclarationLog()
        log.declare("mom", "present")
        self.assertEqual(len(log.all()), 1)
        self.assertFalse(hasattr(log, "retract") or hasattr(log, "delete"))

    def test_since_filters(self):
        log = DeclarationLog()
        d1 = log.declare("mom", "present", timestamp=100.0)
        log.declare("ravi", "present", timestamp=200.0)
        self.assertEqual(log.since(150.0), (log.all()[1],))
        self.assertIn(d1, log.since(50.0))


class ParseDeclarationTest(unittest.TestCase):
    def test_moms_here(self):
        self.assertEqual(parse_declaration("Mom's here"), ("mom", "present"))

    def test_im_alone(self):
        self.assertEqual(parse_declaration("I'm alone"), ("owner", "absent"))
        self.assertEqual(parse_declaration("I am alone."), ("owner", "absent"))

    def test_someone_left(self):
        self.assertEqual(parse_declaration("Ravi left"), ("ravi", "absent"))

    def test_guests(self):
        self.assertEqual(parse_declaration("we have guests tonight"),
                         ("role:guest", "present"))

    def test_private_now_is_absent(self):
        self.assertEqual(parse_declaration("private now"), ("owner", "absent"))

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_declaration("what's the weather"))
        self.assertIsNone(parse_declaration(""))


if __name__ == "__main__":
    unittest.main()
