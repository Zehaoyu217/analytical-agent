from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from slugify import slugify

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.research.schema import (
    PaperFrontmatter,
    dump_center_document,
    load_center_document,
)
from second_brain.schema.claim import ClaimFrontmatter
from second_brain.schema.source import SourceFrontmatter

_AUTO_START = "<!-- sb:auto:start -->"
_AUTO_END = "<!-- sb:auto:end -->"
_PAGE_MARKER_RE = re.compile(r"^<!--\s*page[: ]+\d+\s*-->$", re.IGNORECASE)
_TOC_DOT_LEADER_RE = re.compile(r"(?:\.\s*){3,}\d+\s*$")
_TOC_ENTRY_RE = re.compile(r"(?:^|\s)-\s*\d+(?:\.\d+)+\s")


@dataclass(frozen=True)
class _SummaryParagraph:
    text: str
    is_heading: bool = False


@dataclass(frozen=True)
class CompileCenterReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    paper_ids: tuple[str, ...] = ()


def compile_center(cfg: Config) -> CompileCenterReport:
    cfg.papers_dir.mkdir(parents=True, exist_ok=True)
    sources = list(_iter_sources(cfg))
    claims_by_source = _claims_by_source(cfg)

    created = 0
    updated = 0
    unchanged = 0
    paper_ids: list[str] = []

    for _path, source, body in sources:
        paper = _build_paper(source, body=body, claim_ids=claims_by_source.get(source.id, []))
        paper_ids.append(paper.id)
        target = cfg.papers_dir / f"{paper.id.removeprefix('paper_')}.md"
        action = _upsert_center_doc(target, paper, _paper_body(paper, source_id=source.id))
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1
        else:
            unchanged += 1

    return CompileCenterReport(
        created=created,
        updated=updated,
        unchanged=unchanged,
        paper_ids=tuple(paper_ids),
    )


def _iter_sources(cfg: Config) -> list[tuple[Path, SourceFrontmatter, str]]:
    out: list[tuple[Path, SourceFrontmatter, str]] = []
    if not cfg.sources_dir.exists():
        return out
    for path in sorted(cfg.sources_dir.glob("*/_source.md")):
        meta, body = load_document(path)
        out.append((path, SourceFrontmatter.from_frontmatter_dict(meta), body))
    return out


def _claims_by_source(cfg: Config) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not cfg.claims_dir.exists():
        return out
    for path in sorted(cfg.claims_dir.glob("*.md")):
        if path.parent.name == "resolutions":
            continue
        meta, _body = load_document(path)
        claim = ClaimFrontmatter.from_frontmatter_dict(meta)
        for source_id in claim.supports:
            out.setdefault(source_id, []).append(claim.id)
    for ids in out.values():
        ids.sort()
    return out


def _build_paper(source: SourceFrontmatter, *, body: str, claim_ids: list[str]) -> PaperFrontmatter:
    title_slug = slugify(source.title, lowercase=True, max_length=64) or source.id.removeprefix("src_")
    summary = _summary(source.abstract, body)
    return PaperFrontmatter(
        id=f"paper_{title_slug}",
        title=source.title,
        status="published",
        summary=summary,
        aliases=[],
        tags=list(source.tags),
        confidence=0.85 if source.abstract else 0.70,
        project_ids=[],
        paper_ids=[],
        experiment_ids=[],
        synthesis_ids=[],
        claim_ids=claim_ids,
        source_ids=[source.id],
        updated_at=datetime.now(tz=UTC),
        authors=list(source.authors),
        year=source.year,
        venue="",
    )


def _summary(abstract: str, body: str) -> str:
    if abstract.strip():
        return abstract.strip()
    paragraphs = _summary_paragraphs(body)
    for idx, para in enumerate(paragraphs[:-1]):
        if para.text.lower() == "abstract":
            candidate = paragraphs[idx + 1].text
            if not _looks_structural(candidate):
                return candidate[:500]
    for para in paragraphs:
        if para.is_heading:
            continue
        if _looks_structural(para.text):
            continue
        if _looks_summary_like(para.text):
            return para.text[:500]
    for para in paragraphs:
        if not para.is_heading and not _looks_structural(para.text):
            return para.text[:500]
    return ""


def _summary_paragraphs(body: str) -> list[_SummaryParagraph]:
    out: list[_SummaryParagraph] = []
    for raw_para in body.split("\n\n"):
        lines = [line.strip() for line in raw_para.splitlines()]
        lines = [line for line in lines if line and not _PAGE_MARKER_RE.match(line)]
        if not lines:
            continue
        is_heading = len(lines) == 1 and lines[0].lstrip().startswith("#")
        text = lines[0].lstrip("#").strip() if is_heading else " ".join(lines).strip()
        text = " ".join(text.split()).strip()
        if text:
            out.append(_SummaryParagraph(text=text, is_heading=is_heading))
    return out


def _looks_summary_like(text: str) -> bool:
    word_count = len(text.split())
    return word_count >= 12 or any(ch in text for ch in ".;:?!")


def _looks_structural(text: str) -> bool:
    normalized = " ".join(text.split()).strip()
    lower = normalized.lower()
    if not normalized:
        return True
    if _PAGE_MARKER_RE.fullmatch(normalized):
        return True
    if lower in {"abstract", "contents", "table of contents"}:
        return True
    if _TOC_DOT_LEADER_RE.search(normalized):
        return True
    return bool(_TOC_ENTRY_RE.search(normalized))


def _paper_body(paper: PaperFrontmatter, *, source_id: str) -> str:
    claims = "\n".join(f"- [[{claim_id}]]" for claim_id in paper.claim_ids) or "- none yet"
    auto = "\n".join(
        [
            _AUTO_START,
            "## Summary",
            "",
            paper.summary or "_No summary yet._",
            "",
            "## Evidence",
            "",
            f"- Source: [[{source_id}]]",
            "",
            "## Linked Claims",
            "",
            claims,
            "",
            _AUTO_END,
        ]
    )
    return "\n".join([f"# {paper.title}", "", auto, "", "## Notes", "", ""])


def _upsert_center_doc(path: Path, meta: PaperFrontmatter, body: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        dump_center_document(path, meta, body)
        return "created"

    existing_meta, existing_body = load_center_document(path)
    merged = _merge_auto_block(existing_body, body)
    merged_meta = meta.model_copy(
        update={
            "aliases": list(existing_meta.aliases),
            "tags": sorted(set(existing_meta.tags) | set(meta.tags)),
        }
    )
    if existing_meta.to_frontmatter_dict() == merged_meta.to_frontmatter_dict() and existing_body == merged:
        return "unchanged"
    dump_center_document(path, merged_meta, merged)
    return "updated"


def _merge_auto_block(existing_body: str, new_body: str) -> str:
    start = new_body.find(_AUTO_START)
    end = new_body.find(_AUTO_END)
    if start < 0 or end < 0:
        return new_body
    new_block = new_body[start : end + len(_AUTO_END)]
    cur_start = existing_body.find(_AUTO_START)
    cur_end = existing_body.find(_AUTO_END)
    if cur_start < 0 or cur_end < 0:
        return new_body
    return existing_body[:cur_start] + new_block + existing_body[cur_end + len(_AUTO_END) :]
