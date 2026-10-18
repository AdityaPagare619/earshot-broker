"""Validate household packs against the frozen schema. Fails loudly.

A pack that fails silently is a privacy hole wearing a config file. This tool
is the pack author's first gate and the skeptic's one-command proof: run it,
get a PASS/FAIL per pack, exit 0 only if every pack validates.

Usage:
    earshot-validate-pack [--root DIR] [--lang LANG]

With no flags it validates the shipped packs (base + every language found).
``--root`` points at a third-party packs tree; ``--lang`` validates one
language instead of all.

Exit codes: 0 = every pack valid. 1 = at least one violation (details printed).
2 = the packs tree itself is unusable (missing base, unreadable dir).

Validation reuses the frozen contracts — ``validate_pack()`` for the manifest
and file-split rules, ``load_pack()`` for the cross-file checks (lexicon terms
must name taxonomy topics, renditions must cover the frozen kinds/depths).
This CLI adds reporting and exit codes only; it invents no new rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .schema import validate_pack
from .loader import load_pack
from .yaml_subset import PackError


def _default_packs_root() -> Path:
    """Locate the shipped packs dir, installed or from the source tree."""
    try:
        from importlib.resources import files
        cand = files("earshot.packs")
        if cand.is_dir():
            return Path(str(cand))
    except Exception:
        pass
    return Path(__file__).resolve().parent


def _lang_dirs(root: Path):
    """Language pack dirs: every subdir except 'base' that holds a pack.yaml.

    A subdir that holds pack *files* (*.yaml) but no pack.yaml is returned as
    a (name, None) sentinel — a half-authored pack must fail loudly, never pass
    by being invisible. Subdirs with no pack files at all (tests/,
    __pycache__/, …) are not pack candidates and are ignored.
    """
    found = []
    for child in sorted(root.iterdir()):
        if child.name == "base" or not child.is_dir():
            continue
        if (child / "pack.yaml").is_file():
            found.append(child.name)
        elif any(p.suffix == ".yaml" for p in child.iterdir() if p.is_file()):
            found.append((child.name, None))
    return found


def _check(fn):
    """Run a validation callable. Returns (ok, detail). Never raises."""
    try:
        fn()
    except PackError as exc:
        return False, f"{exc.path}:{exc.line}: {exc.msg}"
    except FileNotFoundError as exc:
        return False, f"missing file: {exc}"
    except Exception as exc:  # noqa: BLE001 — a validator must not traceback
        return False, f"unexpected {type(exc).__name__}: {exc}"
    return True, "ok"


def validate_tree(root: Path, langs=None):
    """Validate base + language packs. Returns [(label, ok, detail)]."""
    results = []
    base_dir = root / "base"
    if not base_dir.is_dir():
        return [("base", False, f"base pack not found under {root}")]
    ok, detail = _check(lambda: validate_pack(base_dir))
    results.append(("base", ok, detail))
    if langs is None:
        langs = []
        unfinished = False
        for entry in _lang_dirs(root):
            if isinstance(entry, tuple):
                unfinished = True
                results.append((entry[0], False,
                                "directory has no pack.yaml — unfinished pack?"))
            else:
                langs.append(entry)
        if not langs and not unfinished:
            results.append(("(no languages)", False,
                            f"no language packs found under {root}"))
    for lang in langs:
        ok, detail = _check(lambda: load_pack(root, lang))
        results.append((lang, ok, detail))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="earshot-validate-pack",
        description="Validate household packs against the frozen schema. "
                    "Fails loudly: exit 1 on any violation.",
    )
    ap.add_argument("--root", default=None,
                    help="packs tree to validate (default: shipped packs)")
    ap.add_argument("--lang", default=None,
                    help="validate one language pack only (default: all)")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else _default_packs_root()
    if not root.is_dir():
        print(f"error: packs root is not a directory: {root}", file=sys.stderr)
        return 2

    langs = [args.lang] if args.lang else None
    if args.lang and not (root / args.lang).is_dir():
        print(f"error: language pack not found: {root / args.lang}",
              file=sys.stderr)
        return 2

    results = validate_tree(root, langs)
    failed = 0
    for label, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {label}: {detail}")
        failed += not ok
    n = len(results)
    print(f"{n - failed}/{n} packs valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
