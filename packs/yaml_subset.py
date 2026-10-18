"""Minimal YAML-subset parser for Household Pack data files.

Deliberately dumber than YAML. Supports ONLY:
  - mappings (2-space indent), e.g.  key: value
  - sequences, e.g.  - item   (including "- key: value" inline mappings)
  - scalars: plain / 'single-quoted' / "double-quoted" strings, ints, floats,
    true/false, null (null, ~, or empty)
  - '#' comments (outside quotes), blank lines

Everything else — tabs, anchors, block scalars (|, >), flow collections ({}, []),
duplicate keys at one level — is a LOUD error. Packs are DATA: this parser never
evaluates anything, imports nothing, and constructs only dict/list/str/int/float/bool/None.

Line numbers are tracked so schema errors can point at the exact line.
"""

from __future__ import annotations


class PackError(Exception):
    """A pack file is malformed or violates the schema. Always loud, always located."""

    def __init__(self, path: str, line: int, msg: str):
        super().__init__(f"{path}:{line}: {msg}")
        self.path = path
        self.line = line
        self.msg = msg


def _strip_comment(text: str) -> str:
    """Remove a '#' comment that is not inside quotes."""
    in_single = in_double = False
    for i, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            # A '#' starts a comment only when preceded by whitespace or at start.
            if i == 0 or text[i - 1] in " \t":
                return text[:i]
    return text


def _parse_scalar(raw: str, path: str, line: int):
    s = raw.strip()
    if s == "" or s in ("null", "~", "Null", "NULL"):
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s and s[0] in "|>":
        raise PackError(path, line, f"block scalars ('{s[0]}') are not supported; keep packs simple")
    if s and s[0] in "{[":
        raise PackError(path, line, "flow collections are not supported; use block style")
    if "\t" in raw:
        raise PackError(path, line, "tabs are not allowed; use 2-space indent")
    return s


def _split_key_value(content: str, path: str, line: int):
    """Split 'key: value' on the first colon that is not inside quotes."""
    in_single = in_double = False
    for i, ch in enumerate(content):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ":" and not in_single and not in_double:
            # Require end-of-content or whitespace after the colon.
            if i + 1 == len(content) or content[i + 1] in " \t":
                key = content[:i].strip()
                val = content[i + 1 :].strip()
                if not key:
                    raise PackError(path, line, "empty mapping key")
                return key, val
    return None, None


class _Parser:
    def __init__(self, path: str, lines):
        self.path = path
        # (indent, content, line_number)
        self.lines = lines
        self.pos = 0

    def peek(self):
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def parse_block(self, indent: int):
        tok = self.peek()
        if tok is None:
            raise PackError(self.path, -1, "unexpected end of file")
        if tok[1].startswith("- ") or tok[1] == "-":
            return self.parse_sequence(indent)
        return self.parse_mapping(indent)

    def parse_mapping(self, indent: int):
        result = {}
        while True:
            tok = self.peek()
            if tok is None or tok[0] != indent:
                break
            ind, content, lineno = tok
            if content.startswith("- ") or content == "-":
                raise PackError(self.path, lineno, "sequence item inside mapping block")
            key, val = _split_key_value(content, self.path, lineno)
            if key is None:
                raise PackError(self.path, lineno, f"expected 'key: value', got: {content!r}")
            if key in result:
                raise PackError(self.path, lineno, f"duplicate key: {key!r}")
            self.pos += 1
            if val != "":
                result[key] = _parse_scalar(val, self.path, lineno)
            else:
                nxt = self.peek()
                if nxt is None or nxt[0] <= indent:
                    # 'key:' with nothing under it -> null (explicit, not silent:
                    # schema validation decides whether null is allowed there).
                    result[key] = None
                else:
                    if nxt[0] != indent + 2:
                        raise PackError(
                            self.path, nxt[2],
                            f"indent must be exactly 2 spaces per level (got {nxt[0]}, want {indent + 2})",
                        )
                    result[key] = self.parse_block(nxt[0])
        return result

    def parse_sequence(self, indent: int):
        items = []
        while True:
            tok = self.peek()
            if tok is None or tok[0] != indent:
                break
            ind, content, lineno = tok
            if not (content.startswith("- ") or content == "-"):
                break
            self.pos += 1
            rest = content[1:].strip() if content != "-" else ""
            if rest == "":
                nxt = self.peek()
                if nxt is None or nxt[0] <= indent:
                    items.append(None)
                else:
                    if nxt[0] != indent + 2:
                        raise PackError(
                            self.path, nxt[2],
                            f"indent must be exactly 2 spaces per level (got {nxt[0]}, want {indent + 2})",
                        )
                    items.append(self.parse_block(nxt[0]))
            else:
                key, val = _split_key_value(rest, self.path, lineno)
                if key is not None:
                    # Inline mapping: "- key: value" starts a mapping whose
                    # continuation lines sit at indent+2.
                    mapping = {}
                    if val != "":
                        mapping[key] = _parse_scalar(val, self.path, lineno)
                    else:
                        nxt = self.peek()
                        if nxt is not None and nxt[0] == indent + 2:
                            mapping[key] = self.parse_block(nxt[0])
                        else:
                            mapping[key] = None
                    # Continuation keys of the same mapping item.
                    while True:
                        nxt = self.peek()
                        if nxt is None or nxt[0] != indent + 2 or nxt[1].startswith("- "):
                            break
                        k2, v2 = _split_key_value(nxt[1], self.path, nxt[2])
                        if k2 is None:
                            raise PackError(self.path, nxt[2], f"expected 'key: value', got: {nxt[1]!r}")
                        if k2 in mapping:
                            raise PackError(self.path, nxt[2], f"duplicate key: {k2!r}")
                        self.pos += 1
                        if v2 != "":
                            mapping[k2] = _parse_scalar(v2, self.path, nxt[2])
                        else:
                            nn = self.peek()
                            if nn is not None and nn[0] == indent + 4:
                                mapping[k2] = self.parse_block(nn[0])
                            elif nn is not None and nn[0] > indent + 2:
                                raise PackError(
                                    self.path, nn[2],
                                    f"indent must be exactly 2 spaces per level (got {nn[0]}, want {indent + 4})",
                                )
                            else:
                                mapping[k2] = None
                    items.append(mapping)
                else:
                    items.append(_parse_scalar(rest, self.path, lineno))
        return items


def parse(text: str, path: str = "<pack>"):
    """Parse YAML-subset text into plain dict/list/scalars. Raises PackError."""
    raw_lines = text.splitlines()
    prepared = []
    for n, raw in enumerate(raw_lines, start=1):
        if "\t" in raw and raw.strip() and not raw.strip().startswith("#"):
            raise PackError(path, n, "tabs are not allowed; use 2-space indent")
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if indent % 2 != 0:
            raise PackError(path, n, f"indent must be a multiple of 2 spaces (got {indent})")
        prepared.append((indent, stripped.strip(), n))
    if not prepared:
        return {}
    parser = _Parser(path, prepared)
    value = parser.parse_block(prepared[0][0])
    if parser.pos != len(prepared):
        tok = prepared[parser.pos]
        raise PackError(path, tok[2], f"unexpected content at indent {tok[0]}: {tok[1]!r}")
    return value


def load_file(path: str):
    """Read and parse a pack file. Raises PackError / OSError."""
    with open(path, "r", encoding="utf-8") as fh:
        return parse(fh.read(), path=path)
