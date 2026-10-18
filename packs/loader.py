"""Household Pack loader: base + language overlay -> one validated Pack.

The loader is the ONLY code that knows languages exist. Everything downstream
consumes the merged Pack object: taxonomy (flattened dotted paths), role
defaults, fallback templates, per-language lexicon and renditions.

Language-blind contract: after loading, the hot path never sees a language
name. It sees (item_id, depth:int, clearance:int) and rendition strings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .schema import validate_lexicon, validate_pack, validate_renditions, validate_ui
from .yaml_subset import load_file


@dataclass(frozen=True)
class Pack:
    """A fully merged, validated household pack."""
    name: str            # language pack name, e.g. "en", "hi"
    version: int
    taxonomy: dict       # {"health.reproductive": {"sensitivity": 0.95}, ...}
    roles: dict          # {"child": {"default_clearance": 1, "topic_overrides": {...}}, ...}
    templates: dict      # fallback boring templates: {kind: {d4..d1: str}}
    lexicon: dict        # per-topic terms+aliases for the leak verifier
    renditions: dict     # per-language renditions: {kind: {d4..d1: str}}
    ui: dict             # UI strings: {cover_suffix, probe_response}


def _flatten_topics(topics, prefix=""):
    flat = {}
    for name, node in topics.items():
        dotted = f"{prefix}.{name}" if prefix else name
        flat[dotted] = {"sensitivity": node["sensitivity"]}
        children = node.get("children") or {}
        flat.update(_flatten_topics(children, dotted))
    return flat


def load_pack(packs_root: str, lang: str) -> Pack:
    """Load and validate base + language pack. Raises PackError on any problem."""
    base_dir = os.path.join(packs_root, "base")
    lang_dir = os.path.join(packs_root, lang)
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"base pack not found: {base_dir}")
    if not os.path.isdir(lang_dir):
        raise FileNotFoundError(f"language pack not found: {lang_dir}")

    base_manifest = validate_pack(base_dir)
    lang_manifest = validate_pack(lang_dir)
    if lang_manifest["inherits"] != base_manifest["name"]:
        from .yaml_subset import PackError
        raise PackError(os.path.join(lang_dir, "pack.yaml"), 0,
                        f"language pack inherits {lang_manifest['inherits']!r}, "
                        f"want {base_manifest['name']!r}")

    taxonomy = _flatten_topics(load_file(os.path.join(base_dir, "taxonomy.yaml"))["topics"])
    roles = load_file(os.path.join(base_dir, "roles.yaml"))["roles"]
    templates = load_file(os.path.join(base_dir, "templates.yaml"))

    lexicon_path = os.path.join(lang_dir, "lexicon.yaml")
    lexicon = load_file(lexicon_path)["lexicon"]
    validate_lexicon({"lexicon": lexicon}, lexicon_path, set(taxonomy))

    renditions_path = os.path.join(lang_dir, "renditions.yaml")
    renditions = load_file(renditions_path)["renditions"]
    validate_renditions({"renditions": renditions}, renditions_path)

    ui_path = os.path.join(lang_dir, "ui.yaml")
    ui = load_file(ui_path)["ui"]
    validate_ui({"ui": ui}, ui_path)

    return Pack(
        name=lang_manifest["name"],
        version=lang_manifest["version"],
        taxonomy=taxonomy,
        roles=roles,
        templates=templates,
        lexicon=lexicon,
        renditions=renditions,
        ui=ui,
    )


def render(pack: Pack, kind: str, depth: str, fields: dict) -> str:
    """Render a depth template for a kind. Falls back to base templates.

    `depth` is one of d1..d4 (d0 is absorbed — the caller never renders it).
    `fields` supplies {placeholder: value}; missing fields render as "".
    This is the ONLY string-producing function the hot path calls.
    """
    table = pack.renditions.get(kind) or pack.templates.get(kind)
    if table is None:
        raise KeyError(f"no templates for kind {kind!r}")
    template = table[depth]
    safe = {k: str(fields.get(k, "")) for k in
            ("title", "time", "daypart", "location", "sender", "items", "category")}
    return template.format(**safe)
