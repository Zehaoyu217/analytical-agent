from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token


@dataclass(frozen=True)
class Heading:
    text: str
    slug: str
    level: int


@dataclass(frozen=True)
class MarkdownLink:
    target: str
    anchor: str | None
    text: str
    line: int  # 1-based source line


@dataclass(frozen=True)
class ParsedDoc:
    path: Path
    rel_path: str
    headings: list[Heading]
    links: list[MarkdownLink]
    front_matter: dict[str, Any]
    raw_text: str


_SLUG_KEEP = re.compile(r"[^a-z0-9\-]+")
_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def slug_for_heading(text: str) -> str:
    """GitHub-style slug: lowercase, spaces → `-`, drop remaining punctuation (keep `-`)."""
    s = text.strip().lower()
    s = s.replace(" ", "-")
    s = _SLUG_KEEP.sub("", s)
    return s


def _strip_front_matter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, text[m.end():]


def _heading_text(tokens: list[Token], idx: int) -> str:
    inline = tokens[idx + 1] if idx + 1 < len(tokens) else None
    if inline is None or inline.type != "inline":
        return ""
    parts: list[str] = []
    for child in inline.children or []:
        if child.type == "text":
            parts.append(child.content)
        elif child.type == "code_inline":
            parts.append(child.content)
    return "".join(parts).strip()


def parse_doc(path: Path, rel_path: str) -> ParsedDoc:
    raw = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _strip_front_matter(raw)
    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(body)

    headings: list[Heading] = []
    links: list[MarkdownLink] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag.lstrip("h"))
            text = _heading_text(tokens, i)
            slug = slug_for_heading(text)
            headings.append(Heading(text=text, slug=slug, level=level))
        elif tok.type == "inline" and tok.children:
            j = 0
            children = tok.children
            line = (tok.map[0] + 1) if tok.map else 0
            while j < len(children):
                ch = children[j]
                if ch.type == "link_open":
                    href = ""
                    for name, value in ch.attrs.items() if isinstance(ch.attrs, dict) else (ch.attrs or []):
                        if name == "href":
                            href = value
                    text_parts: list[str] = []
                    k = j + 1
                    while k < len(children) and children[k].type != "link_close":
                        if children[k].type == "text":
                            text_parts.append(children[k].content)
                        k += 1
                    target = href
                    anchor: str | None = None
                    if "#" in href:
                        target, anchor = href.split("#", 1)
                        anchor = anchor or None
                    links.append(
                        MarkdownLink(
                            target=target,
                            anchor=anchor,
                            text="".join(text_parts).strip(),
                            line=line,
                        )
                    )
                    j = k
                j += 1
        i += 1

    return ParsedDoc(
        path=path,
        rel_path=rel_path,
        headings=headings,
        links=links,
        front_matter=fm,
        raw_text=raw,
    )
