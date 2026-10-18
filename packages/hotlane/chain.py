"""Generalization chains: per-item disclosure depths.

A chain replaces the old fixed 4-level lattice with an item-specific ladder:

    d4: "OB-GYN checkup with Dr. Mehta at 3:40 at Cloudnine"   (full)
    d3: "doctor's appointment at 3:40"                          (generalized)
    d2: "an appointment at 3:40"                                (abstract)
    d1: "something on your calendar this afternoon"            (existence-shape)
    d0: absorbed into the constant-shape suffix                (nothing spoken)

d0 is NOT a spoken level — it means "this item contributes nothing audible."
The hot lane operates on depth INTEGERS only. Rendering a depth to text (for S3's
assembly) is a table lookup, never NLP. This module is language-blind: it never
inspects string contents, only structure.
"""

from __future__ import annotations

from .contracts import GeneralizationChain

# Depth constants. Depths are small ints; d0 means "absorbed, speak nothing".
D4, D3, D2, D1, D0 = 4, 3, 2, 1, 0
DEPTHS = (D4, D3, D2, D1, D0)
SPEAKABLE = (D4, D3, D2, D1)

# Exposure weights: how much each spoken depth leaks toward a secret.
# A2's leakage_weight, kept verbatim — the budget math depends on these.
LEAKAGE_WEIGHT = {D4: 1.0, D3: 0.5, D2: 0.2, D1: 0.05, D0: 0.0}

# Shallowest depth worth speaking. Below this the item is absorbed (d0).
MIN_SPEAK_DEPTH = D1


def validate_chain(chain: GeneralizationChain) -> list[str]:
    """Structural validation only — never inspects string *contents*.

    Returns a list of problem descriptions; empty means valid. Checks:
    depths is a 4-tuple of non-empty strings; renditions maps each language to a
    4-tuple of non-empty strings. Semantic checks (strict-subset, entity leaks)
    belong to S1's deterministic verifier — the hot lane trusts compiled rows.
    """
    problems: list[str] = []
    depths = chain.depths
    if not isinstance(depths, tuple) or len(depths) != 4:
        problems.append(f"depths must be a 4-tuple, got {type(depths).__name__} of len "
                        f"{len(depths) if isinstance(depths, tuple) else '?'}")
    else:
        for i, d in enumerate(depths):
            if not isinstance(d, str) or not d.strip():
                problems.append(f"depths[{i}] must be a non-empty string")
    if not isinstance(chain.renditions, dict) or not chain.renditions:
        problems.append("renditions must be a non-empty dict {lang: 4-tuple}")
    else:
        for lang, rends in chain.renditions.items():
            if not isinstance(rends, tuple) or len(rends) != 4:
                problems.append(f"renditions[{lang!r}] must be a 4-tuple")
            elif any(not isinstance(r, str) or not r.strip() for r in rends):
                problems.append(f"renditions[{lang!r}] must hold non-empty strings")
    return problems


def render(chain: GeneralizationChain, depth: int, lang: str = "en") -> str | None:
    """Table lookup: depth -> pre-verified text. d0 -> None (absorbed).

    Falls back across languages if the requested one is missing (first available),
    because the hot lane must never fail on a missing rendition — it fails toward
    a *shallower* depth instead (caller decides), never toward silence-breaking.
    """
    if depth == D0:
        return None
    if depth not in SPEAKABLE:
        raise ValueError(f"unknown depth {depth!r}")
    idx = D4 - depth  # d4 -> 0, d3 -> 1, d2 -> 2, d1 -> 3
    rends = chain.renditions.get(lang)
    if rends is None:
        # Fallback: first available language. Structure, not content.
        rends = next(iter(chain.renditions.values()))
    return rends[idx]


def leakage_weight(depth: int) -> float:
    """Exposure weight w(d) for the budget accumulator."""
    try:
        return LEAKAGE_WEIGHT[depth]
    except KeyError:
        raise ValueError(f"unknown depth {depth!r}") from None


def is_speakable(depth: int) -> bool:
    return depth in SPEAKABLE and depth >= MIN_SPEAK_DEPTH
