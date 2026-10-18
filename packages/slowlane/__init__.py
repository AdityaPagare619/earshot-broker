"""Sealed-speech slow lane (S1): Seam 1 — Quarantine & Slow Lane.

Nothing uncompiled reaches the hot path. This package implements Stage 1 of the
dataflow pipeline: ingest -> understand -> render -> verify -> compile, with
quarantine as a state machine and a deterministic verifier bounding every
model-shaped output.

stdlib only. packages/kernel/ is frozen and is never imported here — the slow
lane feeds the hot lane TableRows; the kernel consumes them downstream.
"""

from . import (
    compiler,
    confirm,
    models,
    pipeline,
    quarantine,
    render,
    seam,
    translit,
    understand,
    verifier,
)

__all__ = [
    "compiler", "confirm", "models", "pipeline", "quarantine",
    "render", "seam", "translit", "understand", "verifier",
]
