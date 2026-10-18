"""Tests: the deterministic leak verifier (four checks).

The verifier is the load-bearing mechanism of Seam 1: every draft chain —
fixture or LLM — crosses it before becoming speakable.
"""
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))

from earshot.slowlane.models import DraftChain, UnderstandOutput  # noqa: E402
from earshot.slowlane.understand import fixture_lexicon  # noqa: E402
from earshot.slowlane.verifier import TopicLexicon, verify  # noqa: E402


def _understand(**kw):
    base = dict(
        item_id="itm_1", topics=("health", "health.reproductive"),
        entities={"Cloudnine": frozenset({"cloudnine", "क्लाउडनाइन"})},
        sensitive={"Cloudnine": 4},
        sensitive_topics={"health": 3, "health.reproductive": 4},
        sensitivity=0.95, confidence=0.9, lang_detected=("en",),
    )
    base.update(kw)
    return UnderstandOutput(**base)


def _chain(depths_en, renditions=None):
    r = {"en": tuple(depths_en)}
    if renditions:
        r.update(renditions)
    return DraftChain(depths=tuple(depths_en), renditions=r, backend="test")


CLEAN = [
    "OB-GYN checkup with Dr. Mehta at 3:40 at Cloudnine",
    "doctor's appointment at 3:40",
    "an appointment at 3:40",
    "something this afternoon",
]


class EntityCheckTest(unittest.TestCase):
    def test_clean_chain_passes(self):
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon())
        self.assertTrue(v.passed, v.failures)
        self.assertEqual(v.checks_run, 4)

    def test_entity_at_shallow_depth_fails(self):
        leaky = list(CLEAN)
        leaky[1] = "doctor's appointment at Cloudnine at 3:40"  # d3
        v = verify(_chain(leaky), _understand(), fixture_lexicon())
        self.assertFalse(v.passed)
        self.assertTrue(any("entity-leak" in f for f in v.failures))

    def test_entity_allowed_at_d4(self):
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon())
        self.assertTrue(v.passed)

    def test_transliterated_alias_caught(self):
        # THE Hindi-script test: क्लाउडनाइन at d2 must fail even though the
        # Latin "Cloudnine" never appears there.
        leaky = list(CLEAN)
        leaky[1] = "3:40 बजे क्लाउडनाइन में अपॉइंटमेंट"
        v = verify(_chain(leaky), _understand(), fixture_lexicon())
        self.assertFalse(v.passed)
        self.assertTrue(any("entity-leak" in f for f in v.failures), v.failures)

    def test_substring_inside_longer_word_caught(self):
        leaky = list(CLEAN)
        leaky[2] = "appointment at Cloudnine Hospital"  # d2
        v = verify(_chain(leaky), _understand(), fixture_lexicon())
        self.assertFalse(v.passed)

    def test_token_boundary_no_false_positive(self):
        # "ai" must not match inside "said" — boundary-aware matching
        u = _understand(entities={"AI": frozenset({"ai"})}, sensitive={"AI": 4},
                        topics=(), sensitive_topics={})
        chain = _chain(["x", "x", "she said hello", "she said hello"])
        v = verify(chain, u, fixture_lexicon())
        self.assertTrue(all("entity-leak" not in f for f in v.failures),
                        v.failures)


class TopicCheckTest(unittest.TestCase):
    def test_topic_term_below_depth_fails(self):
        leaky = list(CLEAN)
        leaky[1] = "pregnancy checkup at 3:40"  # d3, health.reproductive max_depth=4
        v = verify(_chain(leaky), _understand(), fixture_lexicon())
        self.assertFalse(v.passed)
        self.assertTrue(any("topic-leak" in f for f in v.failures))

    def test_generic_health_term_at_d3_passes(self):
        # "doctor"/"appointment" are health max_depth=3: allowed at d3.
        # This is the canonical generalization — the verifier must not
        # reject the very chain the architecture promises.
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon())
        self.assertTrue(v.passed, v.failures)

    def test_hindi_topic_term_caught(self):
        leaky = list(CLEAN)
        leaky[1] = "3:40 पर गर्भ की जाँच"  # d3 Hindi: "pregnancy checkup"
        v = verify(_chain(leaky), _understand(), fixture_lexicon())
        self.assertFalse(v.passed)
        self.assertTrue(any("topic-leak" in f for f in v.failures), v.failures)

    def test_multilingual_rendition_checked(self):
        chain = _chain(
            CLEAN,
            renditions={"hi": (
                "3:40 पर क्लाउडनाइन में डॉ. मेहता के साथ जांच",
                "3:40 पर डॉक्टर की अपॉइंटमेंट",
                "3:40 पर गर्भ की जाँच",   # d3 hi: pregnancy -> must fail
                "आज दोपहर कुछ है",
            )},
        )
        v = verify(chain, _understand(), fixture_lexicon())
        self.assertFalse(v.passed)
        self.assertTrue(any("[hi]" in f for f in v.failures), v.failures)


class QuasiIdentifierTest(unittest.TestCase):
    def test_repetition_fails(self):
        history = [("afternoon", "tuesday", "clinic", 2)] * 3
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon(),
                   quasi=("afternoon", "tuesday", "clinic"), history=history,
                   quasi_threshold=3)
        self.assertFalse(v.passed)
        self.assertTrue(any("quasi-identifier" in f for f in v.failures))

    def test_below_threshold_passes(self):
        history = [("afternoon", "tuesday", "clinic", 2)] * 2
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon(),
                   quasi=("afternoon", "tuesday", "clinic"), history=history,
                   quasi_threshold=3)
        self.assertTrue(v.passed, v.failures)

    def test_shallow_history_does_not_count(self):
        # d1 exposures are not "revealing"
        history = [("afternoon", "tuesday", "clinic", 1)] * 10
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon(),
                   quasi=("afternoon", "tuesday", "clinic"), history=history,
                   quasi_threshold=3)
        self.assertTrue(v.passed, v.failures)


class MonotonicityTest(unittest.TestCase):
    def test_adding_information_fails(self):
        bad = [
            "OB-GYN checkup with Dr. Mehta at 3:40 at Cloudnine",
            "doctor's appointment at 3:40",
            "an appointment at 3:40 at Cloudnine",  # d2 ADDS Cloudnine
            "something this afternoon",
        ]
        v = verify(_chain(bad), _understand(), fixture_lexicon())
        self.assertFalse(v.passed)
        self.assertTrue(any("monotonicity" in f for f in v.failures))

    def test_clean_chain_monotone(self):
        v = verify(_chain(CLEAN), _understand(), fixture_lexicon())
        self.assertTrue(all("monotonicity" not in f for f in v.failures))


if __name__ == "__main__":
    unittest.main()
