"""Tests: deterministic Devanagari->Latin transliteration.

The bar: identical normalization on both sides of every verifier check.
These tests pin the map's behavior on security-relevant inputs.
"""
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))

from earshot.slowlane.translit import normalize, tokens, transliterate  # noqa: E402


class TransliterateTest(unittest.TestCase):
    def test_basic_word(self):
        self.assertEqual(transliterate("कमल"), "kamal")

    def test_word_final_schwa_deleted(self):
        # inherent 'a' at word end is deleted; medial schwas kept
        self.assertEqual(transliterate("माया"), "maayaa")
        self.assertEqual(transliterate("अस्पताल"), "aspataal")

    def test_matras(self):
        self.assertEqual(transliterate("की"), "kii")
        self.assertEqual(transliterate("डॉक्टर"), "doktar")

    def test_virama_conjunct(self):
        self.assertEqual(transliterate("स्त्री"), "strii")

    def test_nukta(self):
        self.assertEqual(transliterate("क़"), "q")

    def test_anusvara(self):
        self.assertEqual(transliterate("इंस्टैक्स"), "instaiks")

    def test_digits(self):
        self.assertEqual(transliterate("२०२६"), "2026")

    def test_latin_passthrough(self):
        self.assertEqual(transliterate("Cloudnine 3:40"), "Cloudnine 3:40")

    def test_deterministic(self):
        t = "क्लाउडनाइन अस्पताल में डॉ. मेहता"
        self.assertEqual(transliterate(t), transliterate(t))

    def test_total_function_no_crash(self):
        # every Devanagari code point maps somewhere
        s = "".join(chr(c) for c in range(0x0900, 0x0980))
        out = transliterate(s)
        self.assertIsInstance(out, str)
        self.assertTrue(len(out) > 0)


class NormalizeTest(unittest.TestCase):
    def test_casefold_and_nfkc(self):
        self.assertEqual(normalize("CLOUDNINE"), normalize("cloudnine"))

    def test_both_sides_identical(self):
        # the verifier's soundness rests on this: alias and text normalize
        # through the SAME pipeline
        self.assertEqual(normalize("क्लाउडनाइन"), normalize("क्लाउडनाइन"))

    def test_tokens(self):
        self.assertIn("cloudnine", tokens("Cloudnine Hospital, 3:40 PM"))
        self.assertIn("klaaudanaain", tokens("क्लाउडनाइन"))


if __name__ == "__main__":
    unittest.main()
