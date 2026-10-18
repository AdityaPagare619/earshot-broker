"""Tests for the SLO lab (privacy as a falsifiable claim).

Every instrument here has a negative control or a discrimination check:
a meter that cannot fail is theater.

Path handling is robust (no hardcoded worktree paths): the package is
resolved relative to this file.
"""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

from earshot.trace_harness.slo import lexicon as L
from earshot.trace_harness.slo.counterfactuals import run_all as run_counterfactuals
from earshot.trace_harness.slo.households import Episode, generate_households
from earshot.trace_harness.slo.listener import AdversarialListener
from earshot.trace_harness.slo.pareto import run_pareto
from earshot.trace_harness.slo.policies import (
    POLICIES, Spoken, _text, sealed_speech, v1_lattice,
)

SEED = 7
N_HOUSEHOLDS = 4


def leaky_no_withhold(episode, household):
    """NEGATIVE-CONTROL policy: sealed speech with withholding removed.

    Models the regression "the seal silently broke" — every item spoken at
    full depth. The AUC meter MUST catch this (AUC >> 0.5); if it doesn't,
    the meter is theater.
    """
    lang = episode.language
    texts = [_text(it, lang) for it in episode.items]
    return Spoken(voice_text=" ".join(texts), phone_text="", phone_sent=False,
                  mode="full", depths={it.id: 4 for it in episode.items},
                  segments=len(texts))


class SloLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_pareto(seed=SEED, n_households=N_HOUSEHOLDS)
        cls.pts = cls.report["points"]

    # -- the privacy SLO -------------------------------------------------
    def test_sealed_auc_near_half(self):
        auc = self.pts["sealed_speech"]["leakage_auc"]
        self.assertGreaterEqual(auc, 0.45, f"sealed AUC {auc} < 0.45")
        self.assertLessEqual(auc, 0.55, f"sealed AUC {auc} > 0.55")

    def test_v1_leaks_existence(self):
        auc = self.pts["v1_lattice"]["leakage_auc"]
        self.assertGreaterEqual(auc, 0.7,
                                f"v1 AUC {auc}: the EXISTENCE tell should leak")

    def test_native_leaks_everything(self):
        auc = self.pts["native"]["leakage_auc"]
        self.assertGreaterEqual(auc, 0.9, "sanity: the meter must catch native")

    def test_negative_control_meter_fires(self):
        rep = run_pareto(seed=SEED, n_households=N_HOUSEHOLDS,
                         policies={"leaky_no_withhold": leaky_no_withhold})
        auc = rep["points"]["leaky_no_withhold"]["leakage_auc"]
        self.assertGreater(auc, 0.8,
                           f"meter failed to catch a broken seal (AUC {auc})")

    # -- inference near base rate ----------------------------------------
    def test_inference_near_base_rate(self):
        pt = self.pts["sealed_speech"]
        self.assertLessEqual(pt["inference_rate"], pt["inference_base_rate"] + 0.1,
                             "sealed listener infers above base rate")
        native = self.pts["native"]
        self.assertGreaterEqual(native["inference_rate"],
                                native["inference_base_rate"] + 0.2,
                                "sanity: native should be inferable")

    # -- language-blindness: decisions key on labels, never strings --------
    def test_language_blindness(self):
        hh = generate_households(1, SEED)[0]
        for pname, pfn in (("sealed_speech", sealed_speech),
                           ("v1_lattice", v1_lattice)):
            for ep in hh.episodes[:12]:
                blind = _tokenize(ep)
                a, b = pfn(ep, hh), pfn(blind, hh)
                with self.subTest(policy=pname, day=ep.day, slot=ep.slot):
                    self.assertEqual(a.depths, b.depths,
                                     "depths changed under token substitution")
                    self.assertEqual(a.mode, b.mode,
                                     "mode changed under token substitution")

    # -- counterfactuals ---------------------------------------------------
    def test_counterfactuals_sealed_pass(self):
        for r in run_counterfactuals(POLICIES):
            if r.policy == "sealed_speech":
                with self.subTest(suite=r.suite):
                    self.assertTrue(r.passed, r.detail)

    def test_counterfactuals_discriminate(self):
        expected = {
            "sealed_speech": {"content_swap", "remove_item", "add_guest",
                              "replay_alone"},
            "v1_lattice": {"content_swap"},
            "keyword": {"content_swap"},
            "native": set(),
        }
        got = {}
        for r in run_counterfactuals(POLICIES):
            if r.passed:
                got.setdefault(r.policy, set()).add(r.suite)
        self.assertEqual(got.get("sealed_speech", set()),
                         expected["sealed_speech"])
        self.assertEqual(got.get("v1_lattice", set()), expected["v1_lattice"])
        self.assertEqual(got.get("keyword", set()), expected["keyword"])
        self.assertEqual(got.get("native", set()), expected["native"])

    # -- pareto ordering ----------------------------------------------------
    def test_pareto_ordering(self):
        sealed = self.pts["sealed_speech"]["leakage_auc"]
        v1 = self.pts["v1_lattice"]["leakage_auc"]
        self.assertLess(sealed, v1 - 0.2,
                        "sealed must leak far less than v1")
        self.assertGreaterEqual(
            self.pts["sealed_speech"]["owner_utility"],
            self.pts["keyword"]["owner_utility"],
            "sealed utility must beat the naive filter")
        self.assertLess(self.pts["sealed_speech"]["friction"], 0.2,
                        "friction (cover-when-alone) unreasonably high")

    # -- fixture validity ----------------------------------------------------
    def test_secrets_have_non_audiences(self):
        for hh in generate_households(2, SEED):
            self.assertTrue(hh.secrets, "household with no secrets")
            roles = {p.role for p in hh.people}
            for s in hh.secrets:
                with self.subTest(household=hh.name, secret=s.id):
                    self.assertTrue(s.non_audience_roles,
                                    "secret with empty non-audience")
                    # At least one non-audience role must be populated, or the
                    # secret is never actually tested against a listener.
                    self.assertTrue(set(s.non_audience_roles) & roles,
                                    "no non-audience role has a person")


def _tokenize(episode: Episode) -> Episode:
    """Replace every string with an opaque token. Decisions must not change."""
    counter = [0]

    def tok(text):
        counter[0] += 1
        return f"tok_{counter[0]}"

    items = []
    for it in episode.items:
        items.append(type(it)(
            id=it.id, secret=it.secret,
            text={lang: tok(t) for lang, t in it.text.items()},
            time=it.time,
        ))
    return Episode(day=episode.day, slot=episode.slot,
                   language=episode.language, audience=episode.audience,
                   believed_audience=episode.believed_audience,
                   items=tuple(items), uncertain=episode.uncertain)


if __name__ == "__main__":
    unittest.main(verbosity=2)
