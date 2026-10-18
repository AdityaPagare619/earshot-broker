"""End-to-end latency evidence — client-measured round trips (J3).

Methodology (dossier §13.1, decision #64): the 500ms budget is an MCP
client-visible round trip. We measure exactly that: http.client POST ->
response bytes, loopback, warm server, sequential calls, N=200. Kernel-only
timings are NOT reported as latency. Writes evidence/latency.json.
"""
import json
import os
import sys
import statistics
import time
import unittest


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling test helper (harness)
from harness import Client, start_server

PORT = 8896
N = 200
BUDGET_MS = 500.0
EVIDENCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "evidence", "latency.json")


def percentile(data, p):
    data = sorted(data)
    k = (len(data) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(data) - 1)
    return data[f] + (data[c] - data[f]) * (k - f)


class LatencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, _ = start_server(PORT)
        # Four credentials round-robin: the per-token rate limiter (100/min)
        # is production behavior; the latency probe must not trip it.
        cls.clients = []
        for _ in range(4):
            c = Client(PORT, cls.srv.auth.add("house-a", "priya"))
            c.initialize()
            cls.clients.append(c)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_round_trip_latency(self):
        rtts = []
        for i in range(N):
            c = self.clients[i % len(self.clients)]
            args = {"date": "2026-10-19", "timezone": "Asia/Kolkata",
                    "request_key": f"latency-key-{i:06d}"}
            t0 = time.perf_counter()
            b = c.tool("prepare_day_brief", args)
            rtts.append((time.perf_counter() - t0) * 1000)
            self.assertEqual(b["result"]["structuredContent"]["request_state"],
                             "accepted")
        rtts.sort()
        stats = {
            "methodology": ("client-measured HTTP POST->response round trip, "
                            "loopback 127.0.0.1, warm ThreadingHTTPServer, "
                            "sequential, includes TLS-free localhost stack only"),
            "tool": "prepare_day_brief",
            "n": N,
            "budget_ms": BUDGET_MS,
            "p50_ms": round(percentile(rtts, 50), 3),
            "p95_ms": round(percentile(rtts, 95), 3),
            "p99_ms": round(percentile(rtts, 99), 3),
            "max_ms": round(rtts[-1], 3),
            "mean_ms": round(statistics.mean(rtts), 3),
            "server_side_p99_ms": round(
                percentile([e["ms"] for e in self.srv.latencies], 99), 3),
            "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "verdict": "PASS" if percentile(rtts, 99) < BUDGET_MS else "FAIL",
        }
        os.makedirs(os.path.dirname(EVIDENCE), exist_ok=True)
        with open(EVIDENCE, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, indent=2)
        print("\nlatency: " + json.dumps({k: stats[k] for k in
              ("p50_ms", "p95_ms", "p99_ms", "max_ms", "verdict")}))
        self.assertLess(percentile(rtts, 99), BUDGET_MS,
                        f"p99 {percentile(rtts,99):.1f}ms exceeds {BUDGET_MS}ms budget")


if __name__ == "__main__":
    unittest.main(verbosity=2)
