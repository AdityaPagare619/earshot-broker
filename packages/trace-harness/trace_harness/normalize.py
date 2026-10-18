"""Normalize: make independent randomness comparable by shape, not by value.

Per dossier §14.3: random request references must be *independent*, not
identical. So we replace random-looking values with stable tokens before
comparison — and separately assert the raw values were actually independent
(an implementation that echoed the same receipt in both worlds would be a
bug the normalizer must not hide).
"""
import re
from dataclasses import dataclass, field

# token_urlsafe(24) ~ 32 chars [A-Za-z0-9_-]; session ids similar.
_RANDOM_RE = re.compile(r"[A-Za-z0-9_-]{20,}")

# Keys whose values are always treated as opaque random tokens.
_RANDOM_KEYS = {"request_ref", "receipt", "session_id", "mcp-session-id"}

_BUCKETS = [(1, "<1ms"), (10, "<10ms"), (100, "<100ms"),
            (1000, "<1s"), (float("inf"), ">=1s")]


def _bucket(ms: float) -> str:
    for limit, label in _BUCKETS:
        if ms < limit:
            return label
    return ">=1s"


@dataclass
class NormalizedTrace:
    steps: list  # list of {"tool","status","result","timing"}
    random_values: list  # raw random values seen (for the independence check)


def normalize_trace(steps) -> NormalizedTrace:
    random_values = []

    def norm_value(key, value):
        if key in _RANDOM_KEYS and isinstance(value, str):
            random_values.append(value)
            return "<RANDOM>"
        if isinstance(value, str) and _RANDOM_RE.fullmatch(value):
            random_values.append(value)
            return "<RANDOM>"
        if isinstance(value, dict):
            return {k: norm_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [norm_value(key, v) for v in value]
        return value

    normed = []
    for s in steps:
        normed.append({
            "tool": s.tool,
            "status": s.status,
            "result": norm_value("", s.result),
            "timing": _bucket(s.duration_ms),
        })
    return NormalizedTrace(normed, random_values)


def assert_randomness_independent(norm_a: NormalizedTrace,
                                  norm_b: NormalizedTrace) -> None:
    """The raw random values must differ across worlds.

    If both worlds produced byte-identical receipts, either the RNG is broken
    or the server is echoing a constant — both are findings, and normalization
    must not launder them into a PASS.
    """
    set_a, set_b = set(norm_a.random_values), set(norm_b.random_values)
    if set_a and set_a == set_b:
        raise AssertionError(
            "random values identical across worlds — RNG or server is not "
            "generating independent references")
