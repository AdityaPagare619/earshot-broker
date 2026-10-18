"""earshot.kernel — re-export of the FROZEN reference kernel.

Canonical source: ``<repo>/packages/kernel/kernel.py``.

That file is FROZEN: no lane may modify, move, or add files to
``packages/kernel/`` (see docs/seats/pro-packaging/DESIGN.md §3). This module
re-exposes its public names under the ``earshot`` namespace **without copying
or modifying it**: the frozen file is located relative to the installed
``earshot`` package and loaded with :mod:`importlib`.

Public names: ``Kernel``, ``Fact``, ``Label``, ``Context``, ``Lease``.

Resolution covers the documented install story (``pip install -e .`` from a
clone, or running from a source checkout). A non-editable install without the
source tree raises an actionable ``ImportError``.
"""

from __future__ import annotations

import importlib.util as _ilu
import os as _os

__all__ = ["Kernel", "Fact", "Label", "Context", "Lease", "PUBLIC"]


def _frozen_path() -> str:
    here = _os.path.dirname(_os.path.abspath(__file__))  # <root>/src/earshot
    repo_root = _os.path.dirname(_os.path.dirname(here))  # <root>
    return _os.path.join(repo_root, "packages", "kernel", "kernel.py")


def _load():
    path = _frozen_path()
    if not _os.path.isfile(path):
        raise ImportError(
            "earshot.kernel: frozen kernel not found at %s. "
            "Install from a source checkout (`pip install -e .`) so "
            "packages/kernel/kernel.py is present." % path
        )
    spec = _ilu.spec_from_file_location("earshot.kernel._frozen", path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_frozen = _load()

Kernel = _frozen.Kernel
Fact = _frozen.Fact
Label = _frozen.Label
Context = _frozen.Context
Lease = _frozen.Lease
PUBLIC = _frozen.PUBLIC

del _frozen, _load, _frozen_path, _ilu, _os
