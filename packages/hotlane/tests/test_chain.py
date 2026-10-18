"""Tests for the GeneralizationChain model: structure, render, weights."""

import unittest

from earshot.hotlane import (
    D0,
    D1,
    D2,
    D3,
    D4,
    GeneralizationChain,
    is_speakable,
    leakage_weight,
    render,
    validate_chain,
)

from hotlane.tests._helpers import make_chain


class TestValidateChain(unittest.TestCase):
    def test_valid_chain(self):
        self.assertEqual(validate_chain(make_chain()), [])

    def test_depths_must_be_4_tuple(self):
        bad = GeneralizationChain(depths=("a", "b"), renditions={"en": ("a",) * 4})
        problems = validate_chain(bad)
        self.assertTrue(any("depths" in p for p in problems))

    def test_empty_depth_string_rejected(self):
        bad = GeneralizationChain(
            depths=("a", "", "c", "d"), renditions={"en": ("a", "b", "c", "d")})
        self.assertTrue(validate_chain(bad))

    def test_renditions_must_be_nonempty_dict(self):
        bad = GeneralizationChain(depths=("a", "b", "c", "d"), renditions={})
        problems = validate_chain(bad)
        self.assertTrue(any("renditions" in p for p in problems))

    def test_rendition_wrong_arity_rejected(self):
        bad = GeneralizationChain(
            depths=("a", "b", "c", "d"), renditions={"en": ("a", "b")})
        self.assertTrue(validate_chain(bad))

    def test_never_inspects_contents(self):
        # Gibberish / another language validates identically: structure only.
        weird = GeneralizationChain(
            depths=("☃☃", "zzz", "123", "!"),
            renditions={"xx": ("☃☃", "zzz", "123", "!")},
        )
        self.assertEqual(validate_chain(weird), [])


class TestRender(unittest.TestCase):
    def test_depths_map_in_order(self):
        c = make_chain()
        self.assertEqual(render(c, D4), "d4 text")
        self.assertEqual(render(c, D3), "d3 text")
        self.assertEqual(render(c, D2), "d2 text")
        self.assertEqual(render(c, D1), "d1 text")

    def test_d0_is_absorbed(self):
        self.assertIsNone(render(make_chain(), D0))

    def test_missing_language_falls_back(self):
        c = make_chain(lang="hi")
        # Requested 'en' missing -> first available ('hi') used. No failure.
        self.assertEqual(render(c, D4, lang="en"), "d4 text")

    def test_unknown_depth_raises(self):
        with self.assertRaises(ValueError):
            render(make_chain(), 7)


class TestWeights(unittest.TestCase):
    def test_spec_weights(self):
        self.assertEqual(leakage_weight(D4), 1.0)
        self.assertEqual(leakage_weight(D3), 0.5)
        self.assertEqual(leakage_weight(D2), 0.2)
        self.assertEqual(leakage_weight(D1), 0.05)
        self.assertEqual(leakage_weight(D0), 0.0)

    def test_weights_monotone(self):
        ws = [leakage_weight(d) for d in (D4, D3, D2, D1, D0)]
        self.assertEqual(ws, sorted(ws, reverse=True))

    def test_is_speakable(self):
        for d in (D4, D3, D2, D1):
            self.assertTrue(is_speakable(d))
        self.assertFalse(is_speakable(D0))


if __name__ == "__main__":
    unittest.main()
