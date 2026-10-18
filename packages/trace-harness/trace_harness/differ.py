"""Differ: compare normalized public traces, classify differences, verdict.

Difference taxonomy:
  STATUS     — ok vs error between worlds
  TEXT       — a string value differs (potential secret in prose)
  STRUCTURED — keys present in one world but not the other
  COUNT      — array lengths differ (potential count oracle, e.g. # of secrets)

Timing is NOT a verdict channel: bucketed timing is reported as a weak
signal only. A single timing observation cannot distinguish a real channel
from cold start / scheduling noise; systematic skew needs repeated runs and
a statistical test this harness does not claim to be.

Verdict PASS = no secret-dependent difference in the public trace.
A PASS is a necessary condition for the privacy property, not a proof of it.
"""
from dataclasses import dataclass, field


@dataclass
class Difference:
    step_index: int
    tool: str
    channel: str  # STATUS | TEXT | STRUCTURED | COUNT | TIMING
    detail: str


@dataclass
class Verdict:
    passed: bool
    differences: list = field(default_factory=list)
    timing_notes: list = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        if self.passed:
            lines.append("PASS: no secret-dependent difference in the public trace")
        else:
            lines.append(f"FAIL: {len(self.differences)} secret-dependent difference(s)")
            for d in self.differences:
                lines.append(f"  step {d.step_index} {d.tool} [{d.channel}] {d.detail}")
        for d in self.timing_notes:
            lines.append(f"  timing note (weak signal): step {d.step_index} "
                         f"{d.tool}: {d.detail}")
        return "\n".join(lines)


def diff_traces(norm_a, norm_b) -> Verdict:
    diffs = []
    timing = []
    steps_a, steps_b = norm_a.steps, norm_b.steps
    if len(steps_a) != len(steps_b):
        return Verdict(False, [Difference(-1, "*", "COUNT",
            f"trace lengths differ: {len(steps_a)} vs {len(steps_b)}")])
    for i, (sa, sb) in enumerate(zip(steps_a, steps_b)):
        tool = sa["tool"]
        if sa["tool"] != sb["tool"]:
            diffs.append(Difference(i, tool, "STRUCTURED",
                                    f"tool sequence diverged: {sa['tool']} vs {sb['tool']}"))
            continue
        if sa["status"] != sb["status"]:
            diffs.append(Difference(i, tool, "STATUS",
                                    f"{sa['status']} vs {sb['status']}"))
            continue
        if sa["timing"] != sb["timing"]:
            timing.append(Difference(i, tool, "TIMING",
                                     f"{sa['timing']} vs {sb['timing']}"))
        _diff_values(sa["result"], sb["result"], diffs, i, tool, path="$")
    return Verdict(passed=not diffs, differences=diffs, timing_notes=timing)


def _diff_values(va, vb, diffs, i, tool, path):
    if type(va) is not type(vb):
        diffs.append(Difference(i, tool, "STRUCTURED",
                                f"{path}: type {type(va).__name__} vs {type(vb).__name__}"))
        return
    if isinstance(va, dict):
        ka, kb = set(va), set(vb)
        for k in sorted(ka - kb):
            diffs.append(Difference(i, tool, "STRUCTURED",
                                    f"{path}.{k}: present only in world A"))
        for k in sorted(kb - ka):
            diffs.append(Difference(i, tool, "STRUCTURED",
                                    f"{path}.{k}: present only in world B"))
        for k in sorted(ka & kb):
            _diff_values(va[k], vb[k], diffs, i, tool, f"{path}.{k}")
    elif isinstance(va, list):
        if len(va) != len(vb):
            diffs.append(Difference(i, tool, "COUNT",
                                    f"{path}: length {len(va)} vs {len(vb)}"))
        for j, (a, b) in enumerate(zip(va, vb)):
            _diff_values(a, b, diffs, i, tool, f"{path}[{j}]")
        if len(va) < len(vb):
            for j in range(len(va), len(vb)):
                diffs.append(Difference(i, tool, "STRUCTURED",
                                        f"{path}[{j}]: present only in world B: {vb[j]!r}"))
        elif len(vb) < len(va):
            for j in range(len(vb), len(va)):
                diffs.append(Difference(i, tool, "STRUCTURED",
                                        f"{path}[{j}]: present only in world A: {va[j]!r}"))
    elif va != vb:
        channel = "TEXT" if isinstance(va, str) else "STRUCTURED"
        diffs.append(Difference(i, tool, channel,
                                f"{path}: {va!r} vs {vb!r}"))
