from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CodeRefKind = Literal["path", "path_line", "symbol"]


@dataclass(frozen=True)
class CodeRef:
    text: str
    kind: CodeRefKind
    path: str | None
    line: int | None
    symbol: str | None
    source_line: int  # 1-based line in the doc


_PATH_LINE_RE = re.compile(r"`([\w./\-]+\.[A-Za-z]{1,5}):(\d+)`")
_PATH_RE = re.compile(r"`([\w./\-]+/[\w./\-]+\.[A-Za-z]{1,5})`")
_SYMBOL_RE = re.compile(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)`")
_FENCE_RE = re.compile(r"^(?:```|~~~)")


def _strip_code_blocks(text: str) -> list[tuple[int, str]]:
    """Yield `(line_number_1based, content)` for lines OUTSIDE fenced or
    indented code blocks. Inline backticks on a non-code line still flow through."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for idx, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line.lstrip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Indented code block: 4+ leading spaces (or 1 tab) on an otherwise blank-led line
        if line.startswith("    ") or line.startswith("\t"):
            continue
        out.append((idx, line))
    return out


def extract_code_refs(text: str) -> list[CodeRef]:
    refs: list[CodeRef] = []
    seen: set[tuple[str, int, str | None]] = set()
    for line_no, line in _strip_code_blocks(text):
        for m in _PATH_LINE_RE.finditer(line):
            path, line_str = m.group(1), m.group(2)
            key = ("path_line", line_no, f"{path}:{line_str}")
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                CodeRef(
                    text=m.group(0),
                    kind="path_line",
                    path=path,
                    line=int(line_str),
                    symbol=None,
                    source_line=line_no,
                )
            )
        for m in _PATH_RE.finditer(line):
            path = m.group(1)
            key = ("path", line_no, path)
            if key in seen:
                continue
            # Skip if this match is the prefix of a path:line we already captured
            if any(
                r.kind == "path_line" and r.source_line == line_no and r.path == path
                for r in refs
            ):
                continue
            seen.add(key)
            refs.append(
                CodeRef(
                    text=m.group(0),
                    kind="path",
                    path=path,
                    line=None,
                    symbol=None,
                    source_line=line_no,
                )
            )
        for m in _SYMBOL_RE.finditer(line):
            symbol = m.group(1)
            # Symbol pattern requires at least one `.` (enforced by `+` in regex)
            key = ("symbol", line_no, symbol)
            if key in seen:
                continue
            # Skip if symbol overlaps a captured path on the same line
            if any(
                r.source_line == line_no
                and r.path is not None
                and symbol in r.path
                for r in refs
            ):
                continue
            seen.add(key)
            refs.append(
                CodeRef(
                    text=m.group(0),
                    kind="symbol",
                    path=None,
                    line=None,
                    symbol=symbol,
                    source_line=line_no,
                )
            )
    return refs
