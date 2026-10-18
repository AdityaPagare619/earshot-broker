"""Public-trace privacy test harness for MCP servers.

Tests the property that matters to a room-facing host: for paired synthetic
worlds that differ only in a secret, the *public trace* (text, structured
content, resources, metadata) must not differ in any secret-dependent way.

What this does NOT prove: production security, absence of timing channels
(timing is bucketed and reported, not asserted exactly), or real-world listener
detection. A PASS is a necessary condition, not a certificate.
"""

from .worlds import World, WorldPair, builtin_pairs
from .adapters import TraceStep, MCPHttpAdapter, KernelDirectAdapter
from .capture import run_sequence
from .normalize import normalize_trace, NormalizedTrace
from .differ import diff_traces, Verdict, Difference
from .adversarial import adversarial_suite, AdversarialResult

__all__ = [
    "World", "WorldPair", "builtin_pairs",
    "TraceStep", "MCPHttpAdapter", "KernelDirectAdapter",
    "run_sequence",
    "normalize_trace", "NormalizedTrace",
    "diff_traces", "Verdict", "Difference",
    "adversarial_suite", "AdversarialResult",
]

__version__ = "0.1.0"
