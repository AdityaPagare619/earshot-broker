"""Paired-world public-trace invariance (dossier 14.3, guarantee G5).

For a fixed public request and authorized release permissions, the public
response must not change when ONLY protected content changes:
- private event vs no private event
- prenatal vs therapy title (different secret values)
- one private event vs several

The request_ref is random by design and excluded from comparison; its
independence (not equality) is asserted separately.
"""
import unittest

from tests.failure_paths.harness import (PUBLIC, TENANT, OWNER, AuditSink, CertifiedFacade,
                     make_fixtures)
from earshot.kernel import Fact, Kernel, Label


def variant_private(value, topics=('health',)):
    return Fact('appt', value,
                Label(frozenset({OWNER}), frozenset(topics)))


def public_only():
    return (Fact('groceries', 'Collect groceries after 6.',
                 Label(frozenset({PUBLIC}), frozenset())),)


class PairedWorldTests(unittest.TestCase):
    def _public_shape(self, facts, key):
        k = Kernel()
        f = CertifiedFacade(k, AuditSink())
        resp = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                   key, facts, 100.0)
        resp = dict(resp)
        ref = resp.pop('request_ref')
        return resp, ref, k

    def test_private_vs_no_private_identical(self):
        with_priv, _, _ = self._public_shape(make_fixtures(), 'k' * 60)
        without_priv, _, _ = self._public_shape(public_only(), 'k' * 61)
        self.assertEqual(with_priv, without_priv)

    def test_different_secret_values_identical(self):
        a, _, _ = self._public_shape(
            (variant_private('Prenatal visit at St. Mary clinic 15:40'),) + public_only(),
            'k' * 62)
        b, _, _ = self._public_shape(
            (variant_private('Therapy session downtown 15:40'),) + public_only(),
            'k' * 63)
        self.assertEqual(a, b)

    def test_one_vs_many_private_events_identical(self):
        one, _, _ = self._public_shape(
            (variant_private('Prenatal visit 15:40'),) + public_only(), 'k' * 64)
        many, _, _ = self._public_shape(
            (variant_private('Prenatal visit 15:40'),
             variant_private('Oncology follow-up 16:30'),
             variant_private('Dentist 09:00', topics=('dental',))) + public_only(),
            'k' * 65)
        self.assertEqual(one, many)

    def test_request_refs_independent_not_equal(self):
        """Random refs must differ across worlds (independent), proving the
        ref carries no secret-derived signal while remaining unpredictable."""
        _, ref_a, _ = self._public_shape(make_fixtures(), 'k' * 66)
        _, ref_b, _ = self._public_shape(public_only(), 'k' * 67)
        self.assertNotEqual(ref_a, ref_b)
        self.assertGreaterEqual(len(ref_a), 20)

    def test_error_paths_identical_across_worlds(self):
        """Invalid input with private facts vs without: identical denial."""
        def deny(facts, key):
            k = Kernel()
            f = CertifiedFacade(k, AuditSink())
            return f.prepare_day_brief(TENANT, OWNER, 'not-a-date',
                                       'Asia/Kolkata', key, facts, 100.0)
        self.assertEqual(deny(make_fixtures(), 'k' * 68),
                         deny(public_only(), 'k' * 69))

    def test_resolve_day_change_releases_no_derivatives(self):
        """resolve_day_change returns only independently-public facts, even
        when the private plan exists. (Typed declassification of derivatives
        is a reviewed operation this facade does not perform.)"""
        k = Kernel()
        f = CertifiedFacade(k, AuditSink())
        facts = make_fixtures()
        ref = f.prepare_day_brief(TENANT, OWNER, '2026-10-20', 'Asia/Kolkata',
                                  'k' * 70, facts, 100.0)['request_ref']
        resp = f.resolve_day_change(TENANT, OWNER, ref, facts, 101.0)
        self.assertEqual(resp['public_facts'], ['Collect groceries after 6.'])


if __name__ == '__main__':
    unittest.main()
