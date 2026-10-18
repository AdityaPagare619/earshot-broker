"""EARSHOT — a private task broker for Alexa+.

Sealed-speech architecture: private facts stay inside EARSHOT's processing
boundary; the room-facing assistant receives only releasable facts plus an
opaque, owner-bound request reference.

Subpackages (see docs/seats/pro-packaging/DESIGN.md for the import contract):
    earshot.kernel         frozen reference kernel (re-exported, never modified)
    earshot.slowlane       Stage 1 ingest: quarantine, verify, compile
    earshot.hotlane        Stage 3 speak: belief fusion, minimax, constant shape
    earshot.secrecy        secrecy graph + MonotoneGate
    earshot.gateway        MCP server (Streamable HTTP, spec 2025-11-25) + adapters
    earshot.simulator      independent Echo-class web host (simulated, labeled)
    earshot.packs          household packs (data)
    earshot.integration    sealed-speech pipeline + fixture stages
    earshot.trace_harness  privacy SLO lab + paired-world counterfactual harness
    earshot.demo           5-beat demo runner

Entry points: earshot-demo, earshot-server, earshot-sim, earshot
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
