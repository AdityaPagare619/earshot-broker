"""Deterministic Devanagari -> Latin transliteration (stdlib only).

Purpose: the verifier's entity/topic checks must catch sensitive terms written
in Hindi script (e.g. क्लाउडनाइन for "Cloudnine"). There is no ICU here, so
this module hand-rolls a total, deterministic map over the Devanagari block.

Design contract (read before "improving" this):
- BOTH sides of every check — rendition text AND alias/lexicon terms — pass
  through the identical normalize() pipeline. Transliteration need only be
  *consistent*, not linguistically perfect: "डॉक्टर" -> "doktr" on both sides
  still matches. The multilingual burden lives in the alias sets (the pack),
  not in this map.
- Fail-closed asymmetry: schwa handling is deliberately simple (word-final
  inherent-'a' deletion only). Residual schwa noise can only cause
  *over*-matching (false positive -> verifier rejects -> template fallback),
  never under-matching of a true alias. Over-matching fails closed. Documented,
  not accidental.
- Total function: every Devanagari code point maps somewhere; unknown code
  points pass through unchanged (spaces, Latin, punctuation unaffected).
"""

# Independent vowels U+0905..U+0914
INDEPENDENT_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu",
    "ऋ": "ri", "ॠ": "rii", "ऌ": "li", "ॡ": "lii",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}

# Consonants U+0915..U+0939 — base WITHOUT the inherent 'a'
CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    "ळ": "l", "क्ष": "ksh", "ज्ञ": "jny",
}

# Nukta consonants: base consonant + nukta sign -> modified sound
NUKTA = "़"
NUKTA_MAP = {
    "क": "q", "ख": "kh", "ग": "gh", "ज": "z", "झ": "jh",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "फ": "f",
    "य": "y", "र": "r", "ल": "l", "व": "v", "स": "s", "ह": "h",
}

# Dependent vowel signs (matras) U+093E..U+094C — replace the inherent 'a'
MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
    "ृ": "ri", "ॄ": "rii", "ॅ": "e", "े": "e", "ै": "ai",
    "ॉ": "o", "ो": "o", "ौ": "au", "ॆ": "e", "ॊ": "o",
}

VIRAMA = "्"  # halant: kills the inherent vowel

# Misc signs
SIGNS = {
    "ं": "n",   # anusvara (simplified; documented)
    "ँ": "n",   # chandrabindu
    "ः": "h",   # visarga
    "ऽ": "'",   # avagraha
    "ॐ": "om",
}

# Devanagari digits U+0966..U+096F
DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}

# Word-boundary characters: inherent-'a' deletion applies before these and at end
_BOUNDARY = frozenset(" \t\n\r.,;:!?()[]{}\"'/\\|-—–")


def transliterate(text: str) -> str:
    """Devanagari -> ASCII Latin. Deterministic, total, stdlib-only.

    Word-final inherent 'a' is deleted (कमल -> "kamal"). All other schwas are
    kept — see module docstring for why this fails closed.
    """
    pieces: list[str] = []        # output fragments
    inherent: list[bool] = []    # does pieces[i] end with a deletable inherent 'a'?
    n = len(text)
    i = 0

    def flush_boundary() -> None:
        # delete a trailing inherent 'a' at a word boundary
        if pieces and inherent and inherent[-1] and pieces[-1].endswith("a"):
            pieces[-1] = pieces[-1][:-1]
            inherent[-1] = False

    while i < n:
        ch = text[i]
        if ch in _BOUNDARY or not ("\u0900" <= ch <= "\u097F" or ch.isascii()):
            # boundary char or non-Devanagari: boundary first, then pass through
            if ch in _BOUNDARY:
                flush_boundary()
            pieces.append(ch)
            inherent.append(False)
            i += 1
        elif ch in CONSONANTS:
            base = CONSONANTS[ch]
            j = i + 1
            if j < n and text[j] == NUKTA:
                base = NUKTA_MAP.get(ch, base)
                j += 1
            if j < n and text[j] == VIRAMA:
                pieces.append(base)          # explicit halant: no vowel
                inherent.append(False)
                j += 1
            elif j < n and text[j] in MATRAS:
                pieces.append(base + MATRAS[text[j]])
                inherent.append(False)
                j += 1
            elif j < n and text[j] in SIGNS:
                pieces.append(base + "a")
                inherent.append(True)
                # sign handled on next loop iteration
            else:
                pieces.append(base + "a")    # inherent 'a'
                inherent.append(True)
            i = j
        elif ch in INDEPENDENT_VOWELS:
            pieces.append(INDEPENDENT_VOWELS[ch])
            inherent.append(False)
            i += 1
        elif ch in MATRAS:
            # stray matra (no preceding consonant in this pass): emit vowel
            pieces.append(MATRAS[ch])
            inherent.append(False)
            i += 1
        elif ch == VIRAMA:
            i += 1  # stray halant: drop (conservative — nothing emitted)
        elif ch in SIGNS:
            pieces.append(SIGNS[ch])
            inherent.append(False)
            i += 1
        elif ch in DIGITS:
            pieces.append(DIGITS[ch])
            inherent.append(False)
            i += 1
        else:
            # other Devanagari code points (e.g. danda): pass through
            pieces.append(ch)
            inherent.append(False)
            i += 1

    flush_boundary()
    return "".join(pieces)


def normalize(text: str) -> str:
    """The canonical normalization both sides of every verifier check use.

    NFKC -> casefold -> transliterate. Identical input on both sides of a
    comparison is what makes the check sound; see module docstring.
    """
    import unicodedata
    return transliterate(unicodedata.normalize("NFKC", text).casefold())


def tokens(text: str) -> frozenset:
    """Normalized token set for a text: lowercase ASCII tokens."""
    import re
    return frozenset(t for t in re.split(r"[^a-z0-9]+", normalize(text)) if t)
