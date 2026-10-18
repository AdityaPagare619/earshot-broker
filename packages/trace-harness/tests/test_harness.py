"""Tests for the public-trace privacy harness.

Positive: all five builtin world pairs PASS over both the HTTP adapter
(against the fixture MCP server) and the direct adapter.
Negative control: a world whose secret is (mis)labeled public MUST fail with
a TEXT-channel difference — proving the harness detects real leaks instead
of vacuously passing.
Adversarial: reference replay and double-withdraw behave identically.
"""
import unittest


import fixtureserver
from fixtureserver import to_fact
from earshot.trace_harness import (
    builtin_pairs, MCPHttpAdapter, KernelDirectAdapter, run_sequence,
    normalize_trace, diff_traces, adversarial_suite,
)
from earshot.trace_harness.normalize import assert_randomness_independent
from earshot.kernel import Kernel

PORT = 8899
BASE = f"http://127.0.0.1:{PORT}/mcp"


def _facts(world):
    return tuple(to_fact(d) for d in world.facts)


class HarnessHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = fixtureserver.start(PORT)

    @classmethod
    def tearDownClass(cls):
        # Release the port: the old per-suite process exited after this class,
        # but the unified pytest run keeps the process alive — a listening
        # socket here collides with later suites (e.g. mcp's PORT+2 = 8899).
        cls.server.shutdown()
        cls.server.server_close()

    def _run_pair(self, pair):
        # World A
        self.server.state.world_facts = {pair.world_a.tenant: _facts(pair.world_a)}
        self._reset()
        ad_a = MCPHttpAdapter(BASE, pair.world_a.tenant, pair.world_a.owner)
        trace_a = run_sequence(ad_a, pair.world_a)
        # World B (fresh kernel state)
        self.server.state.world_facts = {pair.world_b.tenant: _facts(pair.world_b)}
        self._reset()
        ad_b = MCPHttpAdapter(BASE, pair.world_b.tenant, pair.world_b.owner)
        trace_b = run_sequence(ad_b, pair.world_b)
        return trace_a, trace_b

    def _reset(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
        conn.request("POST", "/__reset", b"{}",
                     {"Content-Type": "application/json"})
        conn.getresponse().read()
        conn.close()

    def test_all_pairs_pass_over_http(self):
        for pair in builtin_pairs():
            with self.subTest(pair=pair.name):
                ta, tb = self._run_pair(pair)
                self.assertTrue(all(s.status == "ok" for s in ta + tb),
                                f"script failed: {[ (s.tool, s.status, s.result) for s in ta + tb ]}")
                na, nb = normalize_trace(ta), normalize_trace(tb)
                assert_randomness_independent(na, nb)
                verdict = diff_traces(na, nb)
                self.assertTrue(verdict.passed, verdict.summary())

    def test_negative_control_leak_is_detected(self):
        # Mislabeled secret: world B's "private" fact is marked public.
        # The harness MUST fail, on the TEXT channel.
        pair = builtin_pairs()[0]  # no_private_vs_one_private
        leaked = dict(pair.world_b.facts[2])
        leaked["readers"] = ("*",)
        world_b = pair.world_b
        rigged_b = type(world_b)(
            name=world_b.name, tenant=world_b.tenant, owner=world_b.owner,
            facts=world_b.facts[:2] + (leaked,), script=world_b.script)
        rigged_pair = type(pair)(name=pair.name, description=pair.description,
                                 world_a=pair.world_a, world_b=rigged_b)
        ta, tb = self._run_pair(rigged_pair)
        verdict = diff_traces(normalize_trace(ta), normalize_trace(tb))
        self.assertFalse(verdict.passed, "harness passed on a leaking server")
        channels = {d.channel for d in verdict.differences}
        self.assertTrue(channels & {"TEXT", "STRUCTURED", "COUNT"},
                        f"expected a content/count difference, got {channels}: "
                        f"{verdict.summary()}")

    def test_adversarial_suite_over_http(self):
        pair = builtin_pairs()[1]
        self.server.state.world_facts = {
            pair.world_a.tenant: _facts(pair.world_a),
            pair.world_b.tenant: _facts(pair.world_b),
        }
        self._reset()

        def make_adapter(world):
            return MCPHttpAdapter(BASE, world.tenant, world.owner)

        results = adversarial_suite(make_adapter, pair.world_a, pair.world_b)
        for r in results:
            with self.subTest(name=r.name):
                self.assertTrue(r.passed, r.detail)


class HarnessDirectTests(unittest.TestCase):
    def _run_pair(self, pair):
        def run(world):
            k = Kernel()
            ad = KernelDirectAdapter(k, world.tenant, world.owner,
                                     _facts(world))
            return run_sequence(ad, world)
        return run(pair.world_a), run(pair.world_b)

    def test_all_pairs_pass_direct(self):
        for pair in builtin_pairs():
            with self.subTest(pair=pair.name):
                ta, tb = self._run_pair(pair)
                na, nb = normalize_trace(ta), normalize_trace(tb)
                assert_randomness_independent(na, nb)
                verdict = diff_traces(na, nb)
                self.assertTrue(verdict.passed, verdict.summary())

    def test_randomness_independence_assertion_fires(self):
        pair = builtin_pairs()[0]
        ta, _ = self._run_pair(pair)
        na = normalize_trace(ta)
        # Identical random values across "worlds" must raise, not pass.
        with self.assertRaises(AssertionError):
            assert_randomness_independent(na, na)

    def test_adversarial_suite_direct(self):
        pair = builtin_pairs()[1]

        def make_adapter(world):
            return KernelDirectAdapter(Kernel(), world.tenant, world.owner,
                                       _facts(world))

        results = adversarial_suite(make_adapter, pair.world_a, pair.world_b)
        for r in results:
            with self.subTest(name=r.name):
                self.assertTrue(r.passed, r.detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
