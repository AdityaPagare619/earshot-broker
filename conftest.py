"""EARSHOT unified test bootstrap.

Makes `python -m pytest` from the repo root run every test with zero
environment variables. Read docs/seats/pro-tests/DESIGN.md for the why.

What it does, in order:
  1. Resolves the repo root from this file's location (pathlib — Windows-safe).
  2. Prepends the source directories to sys.path (deduped, absolute). Each test
     file's own `sys.path.insert(0, own_dir)` still resolves its *sibling*
     helpers (harness, arbiter, …) — conftest never adds test-helper dirs whose
     basenames collide (see below).
  3. Defuses true helper-name collisions (`harness`, `arbiter`, …): every test
     module is collected as an _EvictingModule whose import evicts the
     colliding top-level helper names from sys.modules *immediately before
     that module is imported*. Each test file's own-dir insert then resolves
     its *sibling* helper. This reproduces the old per-suite process isolation
     inside one process: already-imported modules keep their bound references,
     so eviction between (never during) imports is safe.

Deliberately NOT on sys.path (ambiguity guards):
  - apps/simulator      — its tests self-insert; adding it would let the wrong
                          `arbiter` win for tests/races (demonstrated: 9 errors).
  - services/gateway/config — would make top-level `gate` ambiguous
                          (packages/secrecy/gate.py must win).
  - integration/fixtures    — would make top-level `shape` ambiguous
                          (services/gateway/mcp/shape.py must win).

pro-packaging coordination: if `import earshot` succeeds (the packaged layout),
that is logged and nothing changes — this setup is purely additive and the old
top-level names cannot collide with the `earshot` package.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _pytest.python import Module

REPO_ROOT = Path(__file__).resolve().parent

# Source directories, most-specific first. `packages/kernel` precedes `packages/`
# so `from kernel import …` binds the kernel *module* (packages/kernel/kernel.py).
_SOURCE_DIRS = [
    "packages/kernel",
    "packages",
    "packages/hotlane/tests",   # _helpers (hotlane tests carry no path hack)
    "packages/slowlane",
    "packages/secrecy",
    "packages/trace-harness",
    "services/gateway/adapters",
    "services/gateway/mcp",
    "tests/races",              # race scaffolding arbiter (see collision note)
    "demo",                     # five_beats
    ".",                        # repo root: packs.*, integration.*, tests.*
]

for _rel in _SOURCE_DIRS:
    _p = str(REPO_ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# pro-packaging handshake: purely informational, never behavioral.
try:
    import earshot  # noqa: F401
    _PACKAGED = True
except ImportError:
    _PACKAGED = False


def _top_level_imports_of(test_file: Path) -> set[str]:
    """Best-effort parse of unqualified top-level imports in a test module."""
    names: set[str] = set()
    try:
        text = test_file.read_text(encoding="utf-8")
    except OSError:
        return names
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("from ") and " import " in line:
            mod = line[5:].split(" import ")[0].strip()
            if mod and "." not in mod and not mod.startswith("__"):
                names.add(mod.split()[0])
        elif line.startswith("import "):
            for part in line[7:].split(","):
                mod = part.strip().split()[0].split(".")[0]
                if mod and not mod.startswith("__"):
                    names.add(mod)
    return names


def _colliding_helpers() -> set[str]:
    """Top-level helper basenames that exist in 2+ source dirs AND are imported
    unqualified by some test module. Computed, not hardcoded, so future
    seats can't silently reintroduce the ambiguity.

    (Repo-wide stem scan, because the collision isn't always "sibling helpers":
    e.g. apps/simulator/arbiter.py is a *source* file that collides with
    tests/races/arbiter.py.)
    """
    by_stem: dict[str, set[str]] = {}
    for py in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts or ".git" in py.parts:
            continue
        stem = py.stem
        if stem.startswith(("test_", "__")):
            continue
        by_stem.setdefault(stem, set()).add(str(py.parent))
    imported: set[str] = set()
    for test_file in REPO_ROOT.rglob("test_*.py"):
        if "__pycache__" in test_file.parts or ".git" in test_file.parts:
            continue
        imported |= _top_level_imports_of(test_file)
    return {s for s, ds in by_stem.items() if len(ds) > 1 and s in imported}


_COLLIDING = _colliding_helpers()


class _EvictingModule(Module):
    """A pytest Module that evicts colliding top-level helper names from
    sys.modules immediately before *its own* import.

    Why at import time: pytest builds the whole collection tree before
    importing any module, so evicting in pytest_collect_file is a no-op by
    import time. Overriding _getobj (the single import point,
    Module._getobj -> importtestmodule) puts the eviction exactly where the
    old per-suite process boundary was: between module imports, never during.
    """

    def _getobj(self):
        for name in _COLLIDING:
            sys.modules.pop(name, None)
        return super()._getobj()


def pytest_pycollect_makemodule(module_path, parent):
    return _EvictingModule.from_parent(parent, path=module_path)


def pytest_report_header(config):
    return [
        f"earshot test bootstrap: repo_root={REPO_ROOT}",
        f"earshot test bootstrap: packaged_mode={_PACKAGED}",
        f"earshot test bootstrap: evicted_helpers={sorted(_COLLIDING)}",
    ]
