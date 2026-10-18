"""FIXTURE — S3 (constant-shape assembly) stand-in.

Implements the ShapePort: cover-mode assembly where the output SHAPE is a
function of the credible set only, probe-resistant responses, and chunked
turns. The constant-shape property is structural here, not stylistic:

  - no counts, no ordinals ("first… also…")
  - the fixed suffix is ALWAYS appended in cover mode — even when nothing
    was withheld
  - the phone digest is ALWAYS sent in cover mode — the buzz carries no signal
  - screen_depth == spoken depth (screens are rooms)

The real S3 seat wires this into the MCP server response path and the
simulator; this fixture proves the assembly logic against the same Plan type.

All spoken UI strings (cover suffix, probe response) come from the pack —
never hardcoded. A hardcoded English suffix would be a language conditional
in disguise.
"""

from __future__ import annotations

from ..ports import Plan, Response, ShapePort


class FixtureShape(ShapePort):
    """Constant-shape assembly + probe resistance + chunked turns."""

    def __init__(self, pack):
        self.pack = pack
        # From the pack, not from code. See ui.yaml.
        self._cover_suffix = pack.ui["cover_suffix"]
        self._probe_text = pack.ui["probe_response"]

    def assemble(self, plan, rows_by_id, pack, fields_by_id):
        """Plan -> Response. In cover mode the shape depends only on the
        credible set (via plan.cover_mode), never on hidden content."""
        parts = []
        digest_parts = []
        for pi in plan.items:
            row = rows_by_id[pi.item_id]
            fields = fields_by_id[pi.item_id]
            if pi.depth == 0:
                # Fully deferred: nothing spoken, full content to the digest.
                digest_parts.append(self._full_text(row, fields))
                continue
            depth_key = f"d{pi.depth}"
            text = self._render(row, depth_key, fields)
            if pi.action in ("SPEAK", "PHONE"):
                parts.append(text)
            if pi.action in ("PHONE", "DEFER"):
                digest_parts.append(self._full_text(row, fields))
        if plan.cover_mode:
            # Constant shape: spoken items listed plainly (no counts, no
            # ordinals), fixed suffix always appended.
            speak = " ".join(parts)
            if speak:
                speak += " "
            speak += self._cover_suffix
            # The digest is ALWAYS sent in cover mode — even if empty of
            # secrets. The buzz carries no information.
            digest = " ".join(digest_parts) if digest_parts else "(nothing held back)"
            digest = f"[phone digest, silent] {digest}"
        else:
            speak = " ".join(parts) if parts else "Nothing on your calendar."
            digest = " ".join(digest_parts)
            if digest:
                digest = f"[phone digest] {digest}"
        return Response(
            speak=speak,
            structured={
                "speak": speak,
                "speak_policy": "verbatim_no_elaboration",
                "mode": "cover" if plan.cover_mode else "open",
                "followups": ["next", "continue_on_personal_device"] if plan.cover_mode else [],
                "screen_depth": None,  # set per-item by the real S3; fixture: mode-level
            },
            meta={"plan_id": f"pln_{id(plan) % 10000:04d}",
                  "table_version": plan.table_version},
            phone_digest=digest,
        )

    def probe_response(self, query, plan, pack):
        """Probe-resistant answer. The query is accepted but never answered
        from hidden content: the response is identical whether the item
        exists, is sealed, or never existed."""
        return Response(
            speak=self._probe_text,
            structured={
                "speak": self._probe_text,
                "speak_policy": "verbatim_no_elaboration",
                "mode": "cover",
                "followups": ["continue_on_personal_device"],
                "screen_depth": 0,
            },
            meta={"plan_id": f"pln_{id(plan) % 10000:04d}",
                  "table_version": plan.table_version},
            phone_digest="[phone digest, silent] (probe logged; no content disclosed)",
        )

    def chunk(self, plan, n=2):
        """Chunked turns: at most n items per turn + followups. Each chunk is
        a new Plan, so the next turn re-reads belief — the honest mid-stream."""
        chunks = []
        items = list(plan.items)
        for i in range(0, len(items), n):
            sub = items[i:i + n]
            chunks.append(Plan(items=tuple(sub), cover_mode=plan.cover_mode,
                               credible_set=plan.credible_set,
                               table_version=plan.table_version))
        return chunks

    # -- internals ---------------------------------------------------------
    def _render(self, row, depth_key, fields):
        kind = fields.get("kind", "event")
        table = self.pack.renditions.get(kind) or self.pack.templates[kind]
        template = table[depth_key]
        safe = {k: str(fields.get(k, "")) for k in
                ("title", "time", "daypart", "location", "sender", "items", "category")}
        return template.format(**safe)

    def _full_text(self, row, fields):
        return self._render(row, "d4", fields)
