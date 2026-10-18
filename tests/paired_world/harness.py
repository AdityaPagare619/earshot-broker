"""Paired-world harness (dossier §14.3).

A World fixes the public request, public facts, policy and permissions, then
varies exactly one protected dimension. PublicView captures everything an
adversary at the public surface can observe: projected text, receipt public
shape, key sets, byte length, timing samples. Invariance is asserted over the
whole view, never just the string.
"""
import os
import re
import time

from earshot.kernel import Fact, Kernel, Label, PUBLIC

PUB = Label(frozenset({PUBLIC}))
PRIYA = Label(frozenset({'priya'}), frozenset({'health'}))
FAMILY = Label(frozenset({'priya', 'ravi'}), frozenset({'family'}))

PUBLIC_FACTS = (
    Fact('weather', 'Rain is forecast.', PUB),
    Fact('date', 'Today is Sunday.', PUB),
)

TENANT = 'house-a'
OWNER = 'priya'
REQUEST_KEY = 'day-brief'

RECEIPT_RE = re.compile(r'^[A-Za-z0-9_-]{32}$')
TIMING_ITERS = 300
# Order-of-magnitude tripwire only: catches algorithmic blowup, never proves
# constant-time (the kernel is not constant-time; see residual risk R4).
TIMING_RATIO_LIMIT = 10.0

# Upgrade 2: every PublicView appends its timing summary here; flushed to
# evidence/j06-timing-report.json at exit. Descriptive statistics, not a proof.
TIMING_LEDGER = []


def make_world(secret_facts):
    """One world: fixed public facts + one protected variant."""
    return PUBLIC_FACTS + tuple(secret_facts)


def secret(title, location='Clinic'):
    return Fact('appointment', '%s, %s 15:40' % (title, location), PRIYA)


class PublicView:
    """Everything observable from the public surface of one world."""

    def __init__(self, name, facts):
        self.name = name
        self.facts = facts
        self.projection = Kernel.public_projection(facts)
        acc = Kernel().accept(TENANT, OWNER, REQUEST_KEY, facts, 100.0)
        self.receipt = acc['receipt']
        self.shape = {k: v for k, v in acc.items() if k != 'receipt'}
        self.n_bytes = len('|'.join(self.projection).encode('utf-8'))
        self.keys = sorted(f.key for f in facts if PUBLIC in f.label.readers)
        self.timing_ns = self._time_projection()
        TIMING_LEDGER.append({'world': name,
                              'n_private_facts': sum(
                                  1 for f in facts
                                  if PUBLIC not in f.label.readers),
                              **self.timing_summary()})

    def _time_projection(self):
        samples = []
        facts = self.facts
        for _ in range(TIMING_ITERS):
            t0 = time.perf_counter_ns()
            Kernel.public_projection(facts)
            samples.append(time.perf_counter_ns() - t0)
        return samples

    @staticmethod
    def _pct(samples, q):
        s = sorted(samples)
        return s[min(len(s) - 1, int(q * len(s)))]

    def timing_summary(self):
        return {
            'n': len(self.timing_ns),
            'median_ns': self._pct(self.timing_ns, 0.5),
            'p95_ns': self._pct(self.timing_ns, 0.95),
            'max_ns': max(self.timing_ns),
        }

    def check_receipt_format(self):
        return bool(RECEIPT_RE.match(self.receipt))

    def public_dict(self):
        """The adversary-visible dict: projection + shape + sizes (no receipt)."""
        return {
            'projection': list(self.projection),
            'shape': self.shape,
            'n_bytes': self.n_bytes,
            'keys': self.keys,
        }

    def assert_invariant_with(self, other):
        """Raise AssertionError describing the first observable difference."""
        a, b = self.public_dict(), other.public_dict()
        if a != b:
            for k in a:
                if a[k] != b[k]:
                    raise AssertionError(
                        'worlds %r vs %r differ in %r: %r != %r'
                        % (self.name, other.name, k, a[k], b[k]))
        for v in (self, other):
            if not v.check_receipt_format():
                raise AssertionError(
                    'world %r receipt fails format check' % v.name)
        r = self.timing_summary()['median_ns'] / max(
            1, other.timing_summary()['median_ns'])
        if not (1.0 / TIMING_RATIO_LIMIT <= r <= TIMING_RATIO_LIMIT):
            raise AssertionError(
                'worlds %r vs %r timing median ratio %.1f exceeds x%.0f tripwire'
                % (self.name, other.name, r, TIMING_RATIO_LIMIT))
        return True


def check_receipt_independence(views):
    """Receipts across worlds: valid format, no collisions, no shared structure.

    We assert independence (no signal), never byte-identity — the dossier
    forbids identical receipts (§14.3); identical would prove a broken RNG.
    """
    receipts = [v.receipt for v in views]
    assert all(RECEIPT_RE.match(r) for r in receipts), 'receipt format'
    assert len(set(receipts)) == len(receipts), 'receipt collision across worlds'
    # No length/charset signal is possible by construction (fixed 32-char
    # urlsafe alphabet); the check above pins it.
    return True


# Flush the timing ledger at interpreter exit (works under unittest discover).
def _flush_timing_ledger():
    import json
    import os
    from tests import EVIDENCE_DIR
    from tests.support.j06_report import _kernel_sha
    import datetime
    if not TIMING_LEDGER:
        return
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    medians = [e['median_ns'] for e in TIMING_LEDGER]
    payload = {
        'suite': 'timing',
        'generated_utc': datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        'kernel_sha': _kernel_sha(),
        'note': 'Descriptive only. The reference kernel is NOT constant-time; '
                'see docs/threat-model.md R4.',
        'n_worlds': len(TIMING_LEDGER),
        'global_median_ns': sorted(medians)[len(medians) // 2],
        'global_max_ns': max(e['max_ns'] for e in TIMING_LEDGER),
        'worst_median_ratio_vs_fastest': (
            max(medians) / max(1, min(medians))),
        'worlds': TIMING_LEDGER,
    }
    with open(os.path.join(EVIDENCE_DIR, 'j06-timing-report.json'), 'w') as f:
        json.dump(payload, f, indent=2, sort_keys=True)


import atexit as _atexit
_atexit.register(_flush_timing_ledger)
