"""Deterministic parsing of `keep_secret` sentences (S4).

"Never mention the clinic in front of Mom" → non-audience {mom}.
"Don't tell anyone about my interview" → conservative default.

Design rules (DESIGN.md D4/R4):

- We parse the NON-AUDIENCE (the safety-critical part), not the full triple.
  Topic-hint extraction is best-effort and only feeds the proposal's ``reason``.
- ``until`` phrases ("until Friday") are parsed best-effort; on failure the edge
  is persistent until released on the phone — the safe direction.
- Unparseable target → CONSERVATIVE DEFAULT (hidden_from role:guest +
  hidden_from role:child). Tightening is always safe; the cost is annoyance,
  never exposure (SEAT_VERDICT.md P3).
- The parser NEVER decides to loosen. Its output vocabulary is TIGHTEN-only.

Person mentions are kept as lowercase strings ("mom"); role words map to
role:guest / role:child. S2's fusion resolves roles against the household.
"""
from __future__ import annotations

import re
from datetime import date as date_cls
from datetime import timedelta

from .edges import EdgeProposal

ROLE_CHILD = "role:child"
ROLE_GUEST = "role:guest"

#: Conservative default when no non-audience can be parsed.
CONSERVATIVE_DEFAULT = (ROLE_GUEST, ROLE_CHILD)

_ROLE_WORDS = {
    "guest": ROLE_GUEST, "guests": ROLE_GUEST,
    "visitor": ROLE_GUEST, "visitors": ROLE_GUEST,
    "kid": ROLE_CHILD, "kids": ROLE_CHILD,
    "child": ROLE_CHILD, "children": ROLE_CHILD,
    "son": ROLE_CHILD, "daughter": ROLE_CHILD,
}
_ANYONE_WORDS = frozenset({
    "anyone", "everyone", "everybody", "nobody", "no one", "anybody",
})

# "in front of X", "around X", "to X", "with X around", "from X"
# Single-word capture: a greedy two-word capture once produced "maya until"
# from "from Maya until Friday". Person keys are single tokens; role words
# are single tokens. Precision beats recall here — the conservative default
# covers the miss.
_TARGET_RES = [
    re.compile(r"\bin front of\s+(?:the\s+|my\s+)?([a-z]+)"),
    re.compile(r"\baround\s+(?:the\s+|my\s+)?([a-z]+)"),
    re.compile(r"\bfrom\s+(?:the\s+|my\s+)?([a-z]+)"),
    re.compile(r"\bto\s+(?:the\s+|my\s+)?([a-z]+)"),
    re.compile(r"\bwith\s+(?:the\s+|my\s+)?([a-z]+)\s+around\b"),
]

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_UNTIL_RE = re.compile(r"\buntil\s+([a-z]+)")


def _next_weekday(name: str, today: date_cls) -> str | None:
    wd = _WEEKDAYS.get(name)
    if wd is None:
        return None
    delta = (wd - today.weekday()) % 7 or 7
    return (today + timedelta(days=delta)).isoformat()


def _parse_until(text: str, today: date_cls) -> str | None:
    m = _UNTIL_RE.search(text.lower())
    if not m:
        return None
    return _next_weekday(m.group(1), today)


def _normalize_target(raw: str) -> str:
    raw = raw.strip().lower()
    if raw in _ROLE_WORDS:
        return _ROLE_WORDS[raw]
    # Multi-word targets ("my roommate") → keep the head noun as a person key.
    return raw.split()[-1]


def parse_keep_secret(instruction: str,
                      today: date_cls | None = None) -> list[EdgeProposal]:
    """Parse one spoken keep_secret sentence → TIGHTEN proposals.

    Always returns at least one proposal (conservative default). Never raises
    on hostile input — worst case is the default, which is safe.
    """
    today = date_cls.today() if today is None else today
    text = instruction.strip()
    low = text.lower()

    targets: list[str] = []
    for rx in _TARGET_RES:
        m = rx.search(low)
        if m:
            targets.append(_normalize_target(m.group(1)))

    if not targets and any(w in low for w in _ANYONE_WORDS):
        targets = list(CONSERVATIVE_DEFAULT)
        reason = "parse: 'anyone/everyone' → conservative default"
    elif not targets:
        # Last resort scan for bare role words anywhere in the sentence.
        for word in re.findall(r"[a-z]+", low):
            if word in _ROLE_WORDS and _ROLE_WORDS[word] not in targets:
                targets.append(_ROLE_WORDS[word])
        if not targets:
            targets = list(CONSERVATIVE_DEFAULT)
            reason = "parse: no non-audience found → conservative default"
        else:
            reason = "parse: bare role word"
    else:
        reason = "parse: prepositional non-audience"

    until = _parse_until(text, today)
    proposals = []
    for target in targets:
        proposals.append(EdgeProposal(
            type="hidden_from", target=target, until=until,
            confidence=1.0, direction="TIGHTEN",
            reason=f"keep_secret: {reason}",
            claimed_source="declared",
        ))
    return proposals
