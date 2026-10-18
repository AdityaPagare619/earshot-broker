"""BOUNDARY DEMONSTRATIONS — what the reference kernel does NOT enforce.

These tests PASS by documenting a boundary, not by fixing it. Each pins a
verdict finding (F1/F2/F3/F6) so no downstream seat can claim the property
unexamined. Read docs/threat-model.md R1/R2/R3/R6 for the residual risks.
"""
import unittest

from kernel import Fact, Kernel, Label, PUBLIC
from tests.adversarial.actors import PUB, PRIYA, PUBLIC_FACT, SECRET
from tests.support.j06_report import Reporter

reporter = Reporter('boundaries')


def _rec(test, ref, obs, verdict, detail):
    reporter.record(test, ref, obs, verdict, detail)


class BoundaryTests(unittest.TestCase):
    def test_public_labeled_fact_with_secret_key_is_released(self):
        """BOUNDARY (F2): the kernel trusts labels. A fact labeled PUBLIC
        whose *key* carries the secret IS released — label assignment is the
        adapter's trust root, and the adapter contract exists only on paper.

        Residual risk R2: a buggy/malicious adapter labeling clinical records
        PUBLIC leaks by design. Mitigation belongs in the adapter layer (J9)
        and the production gate 'cross-tenant tests cover every store' —
        NOT in this kernel.
        """
        sneaky = Fact('prenatal_visit_1540', 'ok', PUB)
        self.assertEqual(Kernel.public_projection((PUBLIC_FACT, sneaky)),
                         ('Rain is forecast.', 'ok'))
        _rec(self._testMethodName, 'verdict F2 / §6 provenance',
             'PUB-labeled secret-key fact released: labels are trusted input',
             'pass-boundary', {'released': True})

    def test_control_flow_taint_is_not_enforced(self):
        """BOUNDARY (F3): a planner that branches on private data and labels
        the result PUBLIC bypasses the algebra silently. The kernel sees only
        the label it is handed.

        Residual risk R3: relies on planner discipline + review (blueprint §4).
        A test cannot fix this; it can only keep it named.
        """
        private_busy = True  # planner observed a private fact off-kernel
        recommendation = 'slot-a' if private_busy else 'slot-b'
        planner_output = Fact('slot', recommendation, PUB)  # planner's label
        self.assertEqual(Kernel.public_projection((planner_output,)),
                         (recommendation,))
        _rec(self._testMethodName, 'verdict F3 / blueprint §4',
             'control-flow taint invisible to kernel: planner-labeled PUB '
             'output released', 'pass-boundary', {'released': True})

    def test_accept_spoofing_succeeds_without_auth(self):
        """BOUNDARY (F1): accept() takes plaintext tenant/owner. An
        unauthenticated caller can mint a capsule for ANY tenant/owner pair.
        G2 currently rests on the outer auth layer, which does not exist yet.

        Residual risk R1: any MCP server wired directly to this API without
        an auth wrapper ships a confused deputy. Production gate: 'authN/Z
        implemented and reviewed' (blueprint §11) is BLOCKING.
        """
        k = Kernel()
        out = k.accept('house-a', 'priya', 'spoofed',
                       (SECRET,), 100.0)  # no credentials offered or checked
        self.assertEqual(out['state'], 'accepted')
        # ...and the spoofed owner can then open it, because 'authenticated'
        # is also caller-supplied:
        self.assertEqual(
            k.open_private(out['receipt'], 'house-a', 'priya', True, 101.0),
            (SECRET,))
        _rec(self._testMethodName, 'verdict F1 / §5 G2',
             'unauthenticated accept() + caller-supplied authenticated=True '
             'opens a capsule for an arbitrary tenant/owner', 'pass-boundary',
             {'spoofed_accept': True})

    def test_accept_idempotency_returns_victim_receipt_to_attacker(self):
        """BOUNDARY (F1b) — the strongest finding of this suite, verified
        empirically: accept() is idempotent per (tenant, owner, request_key)
        and returns the EXISTING receipt to any caller. An attacker who guesses
        the request key learns the victim's receipt, then reads the capsule
        with caller-supplied authenticated=True. Full capsule read, zero
        credentials.

        Residual risk R1 (critical): G2 'owner separation' does not hold at
        the kernel API layer. The outer auth layer must (a) authenticate
        accept() arguments, (b) never return an existing receipt to a
        non-owner, or (c) both. Until then, request_keys must be treated as
        secret — and they are currently caller-chosen strings.
        """
        k = Kernel()
        victim = k.accept('house-a', 'priya', 'day-brief', (SECRET,), 100.0)
        attacker = k.accept('house-a', 'priya', 'day-brief', (), 101.0)
        self.assertEqual(attacker['receipt'], victim['receipt'])
        self.assertEqual(
            k.open_private(attacker['receipt'], 'house-a', 'priya', True, 102.0),
            (SECRET,))
        _rec(self._testMethodName, 'verdict F1 / §5 G2',
             'attacker guesses request key -> receives victim receipt -> '
             'reads capsule with zero credentials', 'pass-boundary',
             {'full_read_without_credentials': True})

    def test_receipt_is_bearer_token(self):
        """BOUNDARY (F6): whoever holds the receipt and passes auth opens the
        capsule. Receipt handling requirements (never log, never in URLs,
        channel binding) are currently unstated.

        Residual risk R6: if any seat logs tool-call arguments, receipts land
        in logs and G2 degrades to 'whoever reads the logs'.
        """
        k = Kernel()
        r = k.accept('house-a', 'priya', 'req', (SECRET,), 100.0)['receipt']
        # A second party that somehow obtains the receipt string:
        stolen = str(r)
        self.assertEqual(
            k.open_private(stolen, 'house-a', 'priya', True, 101.0), (SECRET,))
        _rec(self._testMethodName, 'verdict F6 / §5 G2',
             'receipt alone (+auth flag) grants access: bearer-token semantics',
             'pass-boundary', {'bearer': True})


if __name__ == '__main__':
    unittest.main(verbosity=2)
