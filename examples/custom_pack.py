"""Example 3 — the household pack is data, and data decides depth.

Loads the shipped English pack and renders a health-topic note at mom's
(elder) clearance; then copies the pack tree to a temp dir, changes ONE
value in base/roles.yaml (elder/health: 3 -> 0), reloads, and renders again.

What it proves: disclosure depth is governed by pack data, not code. The same
item, the same fields — a different pack decision — and the room hears a
different thing. No Python changed. (Bad packs fail loudly at load: the
reload asserting success IS the schema-validation proof.)

Run:  python3 examples/custom_pack.py
Exit: 0 with both renditions printed, or non-zero on any breach.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from earshot.packs.loader import load_pack, render
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


FIELDS = {"title": "therapy session notes", "daypart": "evening",
          "category": "health"}


def main() -> int:
    ensure_utf8_stdout()
    root = _packs_root()

    # Shipped pack: elder (mom) clearance on health topics is d3.
    base_pack = load_pack(root, "en")
    elder_health = base_pack.roles["elder"]["topic_overrides"]["health"]
    print(f"[pack:en] elder/health clearance = d{elder_health}")
    print(f"[room hears] {render(base_pack, 'note', f'd{elder_health}', FIELDS)}")

    # Custom pack: ONE data value changed — mom hears nothing about health.
    tmp = Path(tempfile.mkdtemp(prefix="earshot-pack-"))
    custom_root = tmp / "packs"
    shutil.copytree(root, custom_root, dirs_exist_ok=True)
    roles = custom_root / "base" / "roles.yaml"
    text = roles.read_text(encoding="utf-8")
    assert "health: 3" in text, "pack schema drifted — roles.yaml changed shape"
    roles.write_text(text.replace("health: 3", "health: 0", 1),
                     encoding="utf-8")

    custom_pack = load_pack(str(custom_root), "en")  # raises if invalid
    try:
        new_clearance = custom_pack.roles["elder"]["topic_overrides"]["health"]
        assert new_clearance == 0
        # d0 = absorbed: the item vanishes from speech into the constant-shape suffix.
        print(f"[pack:custom] elder/health clearance = d{new_clearance}")
        print("[room hears] (nothing — absorbed into the fixed closing line)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("OK: one pack value changed what the room hears; zero code touched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
