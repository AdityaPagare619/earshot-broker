"""Paired-world invariance tests — dossier §14.3.

For fixed public request, public facts and permissions, the public view must be
invariant when only protected content/existence changes. Each test cites its
dossier row and records evidence via the J6 reporter.
"""
import random
import unittest

from earshot.kernel import Fact, Kernel, Label, PUBLIC
from tests.paired_world.harness import (
    FAMILY, PRIYA, PUB, PublicView, check_receipt_independence,
    make_world, secret)
from tests.support.j06_report import Reporter

reporter = Reporter('paired-world')


def _rec(test, ref, obs, verdict, detail):
    reporter.record(test, ref, obs, verdict, detail)


class PairedWorldTests(unittest.TestCase):
    def _pair(self, name_a, facts_a, name_b, facts_b, ref):
        va = PublicView(name_a, make_world(facts_a))
        vb = PublicView(name_b, make_world(facts_b))
        va.assert_invariant_with(vb)
        check_receipt_independence((va, vb))
        _rec(self._testMethodName, ref,
             'public view invariant across %r vs %r' % (name_a, name_b),
             'pass', {'timing_a': va.timing_summary(),
                      'timing_b': vb.timing_summary(),
                      'n_bytes': va.n_bytes})
        return va, vb

    def test_no_event_vs_one_event(self):
        """§14.3: no private event vs one private event."""
        self._pair('no-event', (), 'one-event', (secret('Prenatal visit'),),
                   '§14.3 no-event-vs-event')

    def test_title_prenatal_vs_therapy(self):
        """§14.3: counterfactual title swap — the response must not reveal
        which protected title was present (text, counts, status, metadata)."""
        self._pair('prenatal', (secret('Prenatal visit'),),
                   'therapy', (secret('Therapy session'),),
                   '§14.3 title counterfactual')

    def test_title_three_way(self):
        """§14.3: prenatal vs oncology vs therapy — pairwise invariance."""
        worlds = [('prenatal', (secret('Prenatal visit'),)),
                  ('oncology', (secret('Oncology follow-up'),)),
                  ('therapy', (secret('Therapy session'),))]
        views = [PublicView(n, make_world(f)) for n, f in worlds]
        for i in range(len(views)):
            for j in range(i + 1, len(views)):
                views[i].assert_invariant_with(views[j])
        check_receipt_independence(views)
        _rec(self._testMethodName, '§14.3 title counterfactual',
             '3-way title invariance holds', 'pass',
             {'worlds': [n for n, _ in worlds]})

    def test_one_vs_several_private_events(self):
        """§14.3: one private event vs several."""
        self._pair('one', (secret('Prenatal visit'),),
                   'three', (secret('Prenatal visit'), secret('Therapy session'),
                             secret('Dental cleaning'),),
                   '§14.3 count variation')

    def test_reordered_private_records(self):
        """§14.3: reordered private records."""
        a = (secret('Prenatal visit'), secret('Therapy session'))
        b = (secret('Therapy session'), secret('Prenatal visit'))
        self._pair('order-ab', a, 'order-ba', b, '§14.3 reorder')

    def test_different_clinic_locations(self):
        """§14.3: different clinic locations."""
        self._pair('clinic-a', (secret('Prenatal visit', 'North Clinic'),),
                   'clinic-b', (secret('Prenatal visit', 'Harbor Clinic'),),
                   '§14.3 location variation')

    def test_private_error_vs_private_no_match(self):
        """§14.3: a private source error must be indistinguishable from a
        private no-match at the public surface — errors carry no signal."""
        err = Fact('fetch', 'E_CONN_TIMEOUT', PRIYA)
        self._pair('private-error', (err,), 'private-no-match', (),
                   '§14.3 error-vs-nomatch')

    def test_existence_on_vs_off(self):
        """§5 G5: existence-sensitive projection — the event existing at all
        must not change the public view."""
        self._pair('exists', (secret('Prenatal visit'),),
                   'absent', (), '§5 G5 existence invariance')

    def test_family_vs_private_label(self):
        """Label granularity: a family-scoped fact and a private fact both
        stay out of the public projection."""
        fam = Fact('dinner', 'Dinner at 7', FAMILY)
        self._pair('family', (fam,), 'private', (secret('Prenatal visit'),),
                   '§6 label granularity')

    def test_repeated_requests_varying_secret_predicate(self):
        """§14.3: repeated requests where the secret predicate varies —
        every repetition's public view is invariant."""
        variants = [(), (secret('Prenatal visit'),), (secret('Therapy session'),),
                    (secret('Prenatal visit'), secret('Therapy session'))]
        views = [PublicView('rep-%d' % i, make_world(v))
                 for i, v in enumerate(variants)]
        base = views[0]
        for v in views[1:]:
            base.assert_invariant_with(v)
        check_receipt_independence(views)
        _rec(self._testMethodName, '§14.3 repeated requests',
             '%d repetitions invariant' % len(views), 'pass',
             {'n': len(views)})

    def test_public_facts_still_project(self):
        """Sanity: the public facts themselves are visible (utility, not just
        denial) — guards against a degenerate 'deny everything' harness."""
        v = PublicView('sanity', make_world((secret('Prenatal visit'),)))
        self.assertEqual(v.projection, ('Rain is forecast.', 'Today is Sunday.'))
        self.assertEqual(v.shape,
                         {'state': 'accepted',
                          'public_message': 'Your request is queued.'})
        _rec(self._testMethodName, '§14.2 task completion',
             'public facts project; receipt shape stable', 'pass',
             {'projection': list(v.projection)})

    def test_projection_never_releases_nonpublic_over_random_lattice(self):
        """Property: over 300 seeded random fact tuples drawn from a reader
        lattice, public_projection releases exactly the PUBLIC-labeled values
        — no more, no less. Deterministic seed: reproducible, not flaky."""
        rnd = random.Random(20261018)
        people = ['priya', 'ravi', 'mom']
        for trial in range(300):
            facts = []
            for i in range(rnd.randint(1, 6)):
                if rnd.random() < 0.3:
                    readers = frozenset({PUBLIC})
                else:
                    readers = frozenset(rnd.sample(people, rnd.randint(0, 3)))
                facts.append(Fact('k%d' % i, 'v%d' % i,
                                  Label(readers, frozenset({'t%d' % i}))))
            facts = tuple(facts)
            proj = Kernel.public_projection(facts)
            expected = tuple(f.value for f in facts
                             if PUBLIC in f.label.readers)
            self.assertEqual(proj, expected,
                             'trial %d: projection != public-labeled values'
                             % trial)
            for f in facts:
                if PUBLIC not in f.label.readers:
                    self.assertNotIn(f.value, proj,
                                     'trial %d: non-public value released'
                                     % trial)
        _rec(self._testMethodName, '§14.2 unauthorized disclosure rate',
             '300/300 random lattice trials: exact public release', 'pass',
             {'trials': 300, 'seed': 20261018})

    def test_taint_propagates_through_derive_chains(self):
        """Derived-of-derived keeps the intersection: taint is not washed by
        chaining through a public intermediate."""
        from tests.adversarial.actors import PUBLIC_FACT, SECRET
        d1 = Kernel.derive('d1', 'intermediate', (PUBLIC_FACT, SECRET))
        d2 = Kernel.derive('d2', 'final', (d1, PUBLIC_FACT))
        self.assertEqual(d2.label.readers, frozenset({'priya'}))
        self.assertEqual(Kernel.public_projection((d2,)), ())
        _rec(self._testMethodName, '§6.3 label propagation',
             'chained derivation keeps private readers', 'pass', {})

    def test_topics_never_appear_in_projection(self):
        """Label topics are policy metadata, not content: a secret sitting in
        the topics set must never surface in projected text."""
        f = Fact('note', 'ok',
                 Label(frozenset({PUBLIC}), frozenset({'prenatal-secret'})))
        proj = Kernel.public_projection((f,))
        self.assertEqual(proj, ('ok',))
        self.assertNotIn('prenatal-secret', '|'.join(proj))
        _rec(self._testMethodName, '§6.2 canonical objects',
             'topics do not leak into projection text', 'pass', {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
