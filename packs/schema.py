"""Frozen Household Pack schema.

A pack is a directory of inert YAML-subset files. This module validates every
pack against the frozen schema and FAILS LOUDLY on any violation — a broken pack
must scream, because a silently-degraded pack is a privacy hole wearing a config
file. No silent defaults. No unknown keys. No exceptions.

Pack layout:
    packs/<name>/
      pack.yaml        manifest: name, version, inherits, description
      taxonomy.yaml    (base only) topic tree with sensitivities
      roles.yaml       (base only) role defaults + topic overrides
      templates.yaml   (base only) boring fallback templates per kind/depth
      lexicon.yaml     (per language) sensitive terms + aliases per topic
      renditions.yaml  (per language) rendition templates per kind/depth

Frozen value domains:
    ITEM_KINDS   = the frozen Item.kind values from the sealed-speech contracts
    ROLES        = the five known roles (strict in v1)
    DEPTHS       = (d4, d3, d2, d1); d0 is absorbed into the constant-shape suffix
    PLACEHOLDERS = allowed {placeholders} in templates
"""

from __future__ import annotations

import os
import re

from .yaml_subset import PackError, load_file

ITEM_KINDS = ("event", "reminder", "delivery", "note", "message_summary")
ROLES = ("child", "guest", "elder", "partner", "unknown")
DEPTHS = ("d4", "d3", "d2", "d1")
PLACEHOLDERS = ("title", "time", "daypart", "location", "sender", "items", "category")
_TOPIC_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")


def _fail(path, where, msg):
    raise PackError(path, 0, f"{where}: {msg}")


def _check_keys(data, allowed, path, where):
    if not isinstance(data, dict):
        _fail(path, where, f"expected a mapping, got {type(data).__name__}")
    for key in data:
        if key not in allowed:
            _fail(path, where, f"unknown key {key!r} (allowed: {sorted(allowed)})")


def _check_str(value, path, where, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        _fail(path, where, f"expected a non-empty string, got {value!r}")


def _check_depth(value, path, where):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 4:
        _fail(path, where, f"expected an integer clearance depth 0..4, got {value!r}")


def _check_sensitivity(value, path, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        _fail(path, where, f"expected a sensitivity in 0..1, got {value!r}")


def _check_placeholders(template, path, where):
    for name in _PLACEHOLDER_RE.findall(template):
        if name not in PLACEHOLDERS:
            _fail(path, where, f"unknown placeholder {{{name}}} (allowed: {PLACEHOLDERS})")


def validate_manifest(data, path):
    _check_keys(data, {"name", "version", "inherits", "description"}, path, "pack.yaml")
    _check_str(data["name"], path, "pack.yaml:name")
    v = data["version"]
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        _fail(path, "pack.yaml:version", f"expected an integer >= 1, got {v!r}")
    inh = data["inherits"]
    if inh is not None and (not isinstance(inh, str) or not inh.strip()):
        _fail(path, "pack.yaml:inherits", f"expected a pack name or null, got {inh!r}")
    _check_str(data["description"], path, "pack.yaml:description")


def _validate_topic_tree(topics, path, where, seen):
    if not isinstance(topics, dict) or not topics:
        _fail(path, where, "expected a non-empty mapping of topics")
    for name, node in topics.items():
        if not _TOPIC_RE.match(name):
            _fail(path, where, f"bad topic name {name!r} (lowercase letters/digits/underscore)")
        dotted = f"{where}.{name}" if where else name
        if dotted in seen:
            _fail(path, dotted, "duplicate topic path")
        seen.add(dotted)
        if not isinstance(node, dict):
            _fail(path, dotted, f"expected a mapping, got {node!r}")
        _check_keys(node, {"sensitivity", "children"}, path, dotted)
        if "sensitivity" not in node:
            _fail(path, dotted, "missing required 'sensitivity'")
        _check_sensitivity(node["sensitivity"], path, dotted + ".sensitivity")
        if "children" in node and node["children"] is not None:
            _validate_topic_tree(node["children"], path, dotted, seen)


def validate_taxonomy(data, path):
    _check_keys(data, {"topics"}, path, "taxonomy.yaml")
    seen = set()
    _validate_topic_tree(data["topics"], path, "", seen)
    return seen  # dotted topic paths, for cross-file checks


def validate_roles(data, path):
    _check_keys(data, {"roles"}, path, "roles.yaml")
    roles = data["roles"]
    if not isinstance(roles, dict):
        _fail(path, "roles.yaml:roles", "expected a mapping")
    missing = [r for r in ROLES if r not in roles]
    if missing:
        _fail(path, "roles.yaml:roles", f"missing required roles: {missing}")
    for role, node in roles.items():
        if role not in ROLES:
            _fail(path, f"roles.yaml:roles.{role}", f"unknown role (known: {ROLES})")
        _check_keys(node, {"default_clearance", "topic_overrides"}, path, f"roles.{role}")
        if "default_clearance" not in node:
            _fail(path, f"roles.{role}", "missing required 'default_clearance'")
        _check_depth(node["default_clearance"], path, f"roles.{role}.default_clearance")
        for topic, depth in (node.get("topic_overrides") or {}).items():
            _check_depth(depth, path, f"roles.{role}.topic_overrides.{topic}")


def _validate_templates(data, path, where, require_all_kinds):
    kinds = set(data) if isinstance(data, dict) else set()
    if require_all_kinds:
        missing = [k for k in ITEM_KINDS if k not in kinds]
        if missing:
            _fail(path, where, f"missing required kinds: {missing}")
    for kind, node in data.items():
        if kind not in ITEM_KINDS:
            _fail(path, f"{where}.{kind}", f"unknown item kind (known: {ITEM_KINDS})")
        _check_keys(node, set(DEPTHS), path, f"{where}.{kind}")
        for depth in DEPTHS:
            if depth not in node:
                _fail(path, f"{where}.{kind}", f"missing required depth {depth!r}")
            _check_str(node[depth], path, f"{where}.{kind}.{depth}")
            _check_placeholders(node[depth], path, f"{where}.{kind}.{depth}")


def validate_templates(data, path):
    _check_keys(data, {"templates"}, path, "templates.yaml")
    inner = data["templates"]
    if not isinstance(inner, dict):
        _fail(path, "templates.yaml", "expected a mapping of kinds")
    _validate_templates(inner, path, "templates.yaml", require_all_kinds=True)


def validate_lexicon(data, path, topic_paths):
    _check_keys(data, {"lexicon"}, path, "lexicon.yaml")
    inner = data["lexicon"]
    if not isinstance(inner, dict) or not inner:
        _fail(path, "lexicon.yaml", "expected a non-empty mapping of topics")
    data = inner
    for topic, node in data.items():
        if topic not in topic_paths:
            _fail(path, f"lexicon.yaml:{topic}",
                  f"unknown topic (not in taxonomy): {topic!r}")
        _check_keys(node, {"terms", "aliases"}, path, f"lexicon.yaml:{topic}")
        terms = node.get("terms")
        if not isinstance(terms, list) or not terms:
            _fail(path, f"lexicon.yaml:{topic}.terms", "expected a non-empty list of terms")
        for term in terms:
            _check_str(term, path, f"lexicon.yaml:{topic}.terms")
        for alias, expansions in (node.get("aliases") or {}).items():
            _check_str(alias, path, f"lexicon.yaml:{topic}.aliases")
            if not isinstance(expansions, list) or not expansions:
                _fail(path, f"lexicon.yaml:{topic}.aliases.{alias}", "expected a non-empty list")
            for expansion in expansions:
                _check_str(expansion, path, f"lexicon.yaml:{topic}.aliases.{alias}")


def validate_renditions(data, path):
    _check_keys(data, {"renditions"}, path, "renditions.yaml")
    inner = data["renditions"]
    if not isinstance(inner, dict) or not inner:
        _fail(path, "renditions.yaml", "expected a non-empty mapping of kinds")
    _validate_templates(inner, path, "renditions.yaml", require_all_kinds=False)


def validate_ui(data, path):
    _check_keys(data, {"ui"}, path, "ui.yaml")
    inner = data["ui"]
    if not isinstance(inner, dict):
        _fail(path, "ui.yaml", "expected a mapping")
    _check_keys(inner, {"cover_suffix", "probe_response"}, path, "ui.yaml:ui")
    _check_str(inner["cover_suffix"], path, "ui.yaml:ui.cover_suffix")
    _check_str(inner["probe_response"], path, "ui.yaml:ui.probe_response")


# What each pack directory must contain.
BASE_FILES = ("pack.yaml", "taxonomy.yaml", "roles.yaml", "templates.yaml")
LANG_FILES = ("pack.yaml", "lexicon.yaml", "renditions.yaml", "ui.yaml")


def validate_pack(pack_dir):
    """Validate a pack directory. Returns the manifest dict. Raises PackError."""
    name = os.path.basename(pack_dir.rstrip(os.sep))
    manifest_path = os.path.join(pack_dir, "pack.yaml")
    if not os.path.isfile(manifest_path):
        raise PackError(manifest_path, 0, "missing pack.yaml")
    manifest = load_file(manifest_path)
    validate_manifest(manifest, manifest_path)
    if manifest["name"] != name:
        raise PackError(manifest_path, 0,
                        f"manifest name {manifest['name']!r} != directory name {name!r}")

    is_base = manifest["inherits"] is None
    required = BASE_FILES if is_base else LANG_FILES
    for fname in required:
        fpath = os.path.join(pack_dir, fname)
        if not os.path.isfile(fpath):
            raise PackError(fpath, 0, f"missing required file for pack {name!r}")
    # A base pack must not carry language-specific files; a lang pack must not
    # carry base files. The split is structural, not conventional.
    if is_base:
        for fname in LANG_FILES[1:]:
            if os.path.isfile(os.path.join(pack_dir, fname)):
                raise PackError(os.path.join(pack_dir, fname), 0,
                                "base pack must not contain language-specific files")
    else:
        for fname in BASE_FILES[1:]:
            if os.path.isfile(os.path.join(pack_dir, fname)):
                raise PackError(os.path.join(pack_dir, fname), 0,
                                "language pack must not redefine base files")

    topic_paths = set()
    if is_base:
        topic_paths = validate_taxonomy(
            load_file(os.path.join(pack_dir, "taxonomy.yaml")),
            os.path.join(pack_dir, "taxonomy.yaml"))
        validate_roles(load_file(os.path.join(pack_dir, "roles.yaml")),
                       os.path.join(pack_dir, "roles.yaml"))
        validate_templates(load_file(os.path.join(pack_dir, "templates.yaml")),
                           os.path.join(pack_dir, "templates.yaml"))
    return manifest
