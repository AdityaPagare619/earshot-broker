"""Cross-platform console compatibility for EARSHOT entry points.

Windows consoles historically default to a legacy code page (cp1252, cp936,
cp932, …) instead of UTF-8. Printing non-ASCII text — Devanagari renditions in
the Hindi demo, em/en dashes in simulator output — then raises
``UnicodeEncodeError`` and kills the program.

Call :func:`ensure_utf8_stdout` at the top of every entry point (before any
``print``). It is a no-op on POSIX and on already-UTF-8 streams.

Stdlib only. This module will move to ``src/earshot/wincompat.py`` in the
pro-migration packaging lane; entry points import it as a top-level module
with the repo root on ``sys.path``.
"""

from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 when the platform allows it.

    Safe to call unconditionally: guarded against old Pythons (<3.7, no
    ``reconfigure``), redirected/non-reconfigurable streams, and any
    unexpected failure (falls back silently — never worse than before).
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            # E.g. stream already closed, or a pytest capture wrapper that
            # rejects reconfigure. Printing in the ambient encoding is the
            # pre-existing behavior; never crash here.
            continue
