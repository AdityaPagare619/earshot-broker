"""F6: coarse timing parity.

A denial that returns 100x faster (or slower) than the success path is a
timing oracle for existence. This is a COARSE bound (10x), not a
constant-time proof — the reference kernel explicitly does not implement
constant-time transport (dossier 14.3). Labeled limitation, not faked proof.
"""
import time
import unittest

from harness import (TENANT, OWNER, AuditSink, CertifiedFacade, make_fixtures)
from kernel import Kernel


def fastest(fn, rounds=15):
    best = float('inf')
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        best = min(best, dt)
    return best


class TimingParityTests(unittest.TestCase):
    def setUp(self):
        self.k = Kernel()
        self.audit = AuditSink()
        self.facade = CertifiedFacade(self.k, self.audit)

    def test_accept_private_vs_empty_timing_parity(self):
        """accept() with private facts vs no facts: no gross timing oracle."""
        private = make_fixtures()
        t_private = fastest(lambda: self.k.accept(
            TENANT, OWNER, 'k-timing-1', private, 100.0))
        k2 = Kernel()
        t_empty = fastest(lambda: k2.accept(
            TENANT, OWNER, 'k-timing-2', (), 100.0))
        ratio = max(t_private, t_empty) / max(min(t_private, t_empty), 1e-9)
        self.assertLess(ratio, 10.0,
                        f'timing oracle risk: private={t_private:.6f}s '
                        f'empty={t_empty:.6f}s ratio={ratio:.1f}')

    def test_open_private_success_vs_failure_timing_parity(self):
        k = Kernel()
        facts = make_fixtures()
        receipt = k.accept(TENANT, OWNER, 'k-timing-3', facts, 100.0)['receipt']

        def ok():
            return k.open_private(receipt, TENANT, OWNER, True, 101.0)

        def denied():
            try:
                k.open_private('no-such', TENANT, OWNER, True, 101.0)
            except PermissionError:
                pass

        t_ok = fastest(ok)
        t_denied = fastest(denied)
        ratio = max(t_ok, t_denied) / max(min(t_ok, t_denied), 1e-9)
        self.assertLess(ratio, 10.0,
                        f'timing oracle risk: ok={t_ok:.6f}s '
                        f'denied={t_denied:.6f}s ratio={ratio:.1f}')

    def test_denial_paths_complete_quickly(self):
        """Denials must not hang: every facade denial completes under 1s."""
        f = self.facade
        facts = make_fixtures()
        cases = [
            lambda: f.prepare_day_brief(TENANT, OWNER, 'bad', 'Asia/Kolkata',
                                        'k' * 50, facts, 100.0),
            lambda: f.resolve_day_change(TENANT, OWNER, 'nope', facts, 100.0),
            lambda: f.withdraw_request(TENANT, OWNER, 'nope', 100.0),
        ]
        for fn in cases:
            t0 = time.perf_counter()
            fn()
            self.assertLess(time.perf_counter() - t0, 1.0)


if __name__ == '__main__':
    unittest.main()
