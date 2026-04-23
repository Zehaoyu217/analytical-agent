from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PAGE_RE = re.compile(
    r"^\s*(?:<!--\s*page[: ]+(\d+)\s*-->|(?:page|p\.)\s+(\d+)\s*$|\[\s*page\s+(\d+)\s*\])\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    source_id: str
    ordinal: int
    section_title: str
    text: str
    start_char: int
    end_char: int
    page_start: int | None = None
    page_end: int | None = None

    @property
    def page_span(self) -> str:
        if self.page_start is None:
            return ""
        if self.page_end is None or self.page_end == self.page_start:
            return f"p.{self.page_start}"
        return f"pp.{self.page_start}-{self.page_end}"


@dataclass(frozen=True)
class _Paragraph:
    text: str
    section_title: str
    page_start: int | None
    page_end: int | None
    start_char: int
    end_char: int


def build_chunks(
    source_id: str,
    body: str,
    *,
    max_chars: int = 1400,
    min_chars: int = 350,
) -> list[ChunkRecord]:
    paragraphs = _paragraphs(body)
    if not paragraphs:
        return []

    chunks: list[ChunkRecord] = []
    pending: list[_Paragraph] = []
    ordinal = 1

    for para in paragraphs:
        candidate_chars = sum(len(p.text) for p in pending) + len(para.text)
        if pending and candidate_chars > max_chars and sum(len(p.text) for p in pending) >= min_chars:
            chunks.append(_flush_chunk(source_id, ordinal, pending))
            ordinal += 1
            pending = [para]
            continue
        pending.append(para)

    if pending:
        chunks.append(_flush_chunk(source_id, ordinal, pending))
    return chunks


def write_chunk_manifest(path: Path, chunks: list[ChunkRecord]) -> None:
    payload = []
    for chunk in chunks:
        data = asdict(chunk)
        data["page_span"] = chunk.page_span
        payload.append(data)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_chunk_manifest(path: Path) -> list[ChunkRecord]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[ChunkRecord] = []
    for item in raw:
        item = dict(item)
        item.pop("page_span", None)
        out.append(ChunkRecord(**item))
    return out


def _paragraphs(body: str) -> list[_Paragraph]:
    lines = body.splitlines()
    section_title = ""
    current_page: int | None = None
    page_detected = False
    current_text: list[str] = []
    current_start: int | None = None
    current_pages: list[int] = []
    offset = 0
    out: list[_Paragraph] = []

    def flush() -> None:
        nonlocal current_text, current_start, current_pages
        if not current_text or current_start is None:
            current_text = []
            current_start = None
            current_pages = []
            return
        text = "\n".join(current_text).strip()
        if text:
            out.append(
                _Paragraph(
                    text=text,
                    section_title=section_title,
                    page_start=min(current_pages) if current_pages else None,
                    page_end=max(current_pages) if current_pages else None,
                    start_char=current_start,
                    end_char=current_start + len(text),
                )
            )
        current_text = []
        current_start = None
        current_pages = []

    for line in lines:
        heading_match = _HEADING_RE.match(line)
        page_match = _PAGE_RE.match(line)
        if "\f" in line:
            page_detected = True
            flush()
            parts = line.split("\f")
            for idx, part in enumerate(parts):
                if idx > 0:
                    current_page = 1 if current_page is None else current_page + 1
                if part.strip():
                    if current_start is None:
                        current_start = offset
                    current_text.append(part)
                    if current_page is not None:
                        current_pages.append(current_page)
            offset += len(line) + 1
            continue
        if page_match:
            flush()
            page_detected = True
            current_page = int(next(group for group in page_match.groups() if group))
            offset += len(line) + 1
            continue
        if heading_match:
            flush()
            section_title = heading_match.group(2).strip()
            offset += len(line) + 1
            continue
        if not line.strip():
            flush()
            offset += len(line) + 1
            continue
        if current_start is None:
            current_start = offset
        current_text.append(line)
        if page_detected and current_page is not None:
            current_pages.append(current_page)
        offset += len(line) + 1
    flush()
    return out


def _flush_chunk(source_id: str, ordinal: int, paragraphs: list[_Paragraph]) -> ChunkRecord:
    text = "\n\n".join(p.text for p in paragraphs)
    section_title = next((p.section_title for p in paragraphs if p.section_title), "")
    page_values = [p.page_start for p in paragraphs if p.page_start is not None]
    page_end_values = [p.page_end for p in paragraphs if p.page_end is not None]
    return ChunkRecord(
        id=f"chk_{source_id.removeprefix('src_')}_{ordinal:03d}",
        source_id=source_id,
        ordinal=ordinal,
        section_title=section_title,
        text=text,
        start_char=min(p.start_char for p in paragraphs),
        end_char=max(p.end_char for p in paragraphs),
        page_start=min(page_values) if page_values else None,
        page_end=max(page_end_values) if page_end_values else None,
    )
