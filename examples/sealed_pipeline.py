"""Example 2 — one secret through all three seams, computed.

Drives the sealed-speech pipeline directly: a therapy note (high sensitivity)
and a team standup (public) are ingested, quarantined, compiled; then mom
walks in, and the pipeline briefs the room.

What it proves: with a non-empty room, the secret's spoken depth drops below
full detail, its title never appears in the spoken text, and the private
content is routed to the phone digest instead — all computed, not narrated.

[FIXTURE] stage mechanisms are deterministic stand-ins (see FINAL-ARCHITECTURE.md).

Run:  python3 examples/sealed_pipeline.py
Exit: 0 with the room/phone split printed, or non-zero on any breach.
"""

from __future__ import annotations

import os

from earshot.integration.pipeline import SealedSpeechPipeline
from earshot.packs.loader import load_pack
from earshot.wincompat import ensure_utf8_stdout


def _packs_root() -> str:
    try:
        from importlib.resources import files
        cand = files("earshot.packs")
        if cand.is_dir():
            return str(cand)
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "packs")


def main() -> int:
    ensure_utf8_stdout()
    pack = load_pack(_packs_root(), "en")
    pipe = SealedSpeechPipeline(pack)

    # Seam 1 — QUARANTINE: everything ingested is suspect until compiled.
    therapy_id = pipe.ingest("note", {
        "title": "therapy session notes", "daypart": "evening",
        "category": "health"}, source="notes")
    pipe.ingest("event", {"title": "team standup", "time": "10 AM",
                          "daypart": "morning", "category": "work"},
                source="calendar")
    compiled, _ = pipe.compile_all()
    assert therapy_id in compiled, "therapy note stuck in quarantine"

    # Seam 2 — SEAL: the owner draws a line, then mom walks in.
    edge = pipe.keep_secret("never mention my therapy in front of mom")
    assert edge is not None, "keep_secret instruction not parsed"
    print(f"[seal] keep_secret -> {edge.type} edge ({edge.target})")
    changed = pipe.room("mom's here")
    print(f"[room] {changed}")
    response, info = pipe.brief()

    plan = info["plan"]
    therapy_depth = next(pi.depth for pi in plan.items
                         if pi.item_id == therapy_id)
    print(f"[plan] therapy note planned at depth d{therapy_depth} "
          f"(credible room: {sorted(plan.credible_set)})")
    print(f"[speak] {response.speak}")
    print(f"[phone] {response.phone_digest or '(no digest)'}")

    # Seam 3 — CONSTANT SHAPE: the secret is withheld from speech entirely and
    # routed to the personal channel; the room hears a fixed-shape turn.
    assert therapy_depth == 0, f"secret not fully sealed: d{therapy_depth}"
    assert "therapy" not in response.speak.lower(), "secret leaked into speech"
    assert "therapy session notes" in response.phone_digest, \
        "withheld content never reached the phone"

    print("OK: secret sealed from the room, delivered to the phone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
