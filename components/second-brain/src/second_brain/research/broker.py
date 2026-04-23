from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.index.retriever import RetrievalHit, make_retriever
from second_brain.research.schema import (
    CenterDocument,
    CenterKind,
    ProjectFrontmatter,
    iter_center_documents,
)
from second_brain.store.fts_store import FtsStore

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class BrokerHit:
    id: str
    kind: str
    title: str
    score: float
    matched_field: str
    summary: str = ""
    evidence: list[RetrievalHit] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    section_title: str = ""
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class BrokerSearchResult:
    hits: list[BrokerHit]
    active_project_id: str | None = None


def broker_search(
    cfg: Config,
    *,
    query: str,
    k: int = 10,
    scope: str = "both",
    project_id: str | None = None,
    with_neighbors: bool = False,
) -> BrokerSearchResult:
    query = query.strip()
    if not query:
        return BrokerSearchResult(hits=[], active_project_id=project_id)

    center_docs = iter_center_documents(cfg)
    center_by_id = {doc.id: doc for _path, doc, _body in center_docs}
    linked_index = _linked_center_index(center_docs)
    active_project_id = project_id or _default_project_id(center_docs)
    active_project_links = _active_project_links(center_by_id.get(active_project_id))
    candidates: dict[str, BrokerHit] = {}

    direct_center_hits = _search_center_fts(cfg, query=query, k=max(k * 2, 10))
    for hit in direct_center_hits:
        doc = center_by_id.get(hit["id"])
        if doc is None:
            continue
        score = float(hit["score"]) + _project_boost(doc, active_project_id, active_project_links)
        candidates[doc.id] = BrokerHit(
            id=doc.id,
            kind=doc.kind.value,
            title=doc.title,
            score=score,
            matched_field=hit["matched_field"],
            summary=doc.summary,
            evidence=[],
            project_ids=list(doc.project_ids),
            source_ids=list(doc.source_ids),
            claim_ids=list(doc.claim_ids),
        )

    side_hits: list[RetrievalHit] = []
    if cfg.fts_path.exists():
        retriever = make_retriever(cfg)
        side_hits = retriever.search(
            query,
            k=max(k * 3, 12),
            scope=scope,  # type: ignore[arg-type]
            with_neighbors=with_neighbors,
        )

    for hit in side_hits:
        linked_ids = linked_index.get(hit.id, [])
        if hit.kind == "chunk" and hit.source_id:
            linked_ids = linked_ids + linked_index.get(hit.source_id, [])
        if linked_ids:
            linked_ids = list(dict.fromkeys(linked_ids))
        if linked_ids:
            for center_id in linked_ids:
                doc = center_by_id.get(center_id)
                if doc is None:
                    continue
                existing = candidates.get(center_id)
                base = existing.score if existing is not None else 0.0
                score = max(
                    base,
                    hit.score * 0.95 + _project_boost(doc, active_project_id, active_project_links),
                )
                evidence = list(existing.evidence) if existing is not None else []
                evidence.append(hit)
                candidates[center_id] = BrokerHit(
                    id=doc.id,
                    kind=doc.kind.value,
                    title=doc.title,
                    score=score,
                    matched_field="linked_evidence",
                    summary=doc.summary,
                        evidence=evidence[:4],
                        project_ids=list(doc.project_ids),
                        source_ids=list(doc.source_ids),
                        claim_ids=list(doc.claim_ids),
                        section_title=existing.section_title if existing else "",
                        page_start=existing.page_start if existing else None,
                        page_end=existing.page_end if existing else None,
                    )
        else:
            existing = candidates.get(hit.id)
            score = max(existing.score if existing else 0.0, hit.score)
            summary = _summary_for_side_hit(cfg, hit)
            title = _title_for_side_hit(cfg, hit)
            evidence = list(existing.evidence) if existing is not None else []
            if hit.kind in {"claim", "source"}:
                evidence.append(hit)
            candidates[hit.id] = BrokerHit(
                id=hit.id,
                kind=hit.kind,
                title=title,
                score=score,
                matched_field=hit.matched_field,
                summary=summary,
                evidence=evidence[:4],
                project_ids=[],
                source_ids=[hit.source_id or hit.id] if hit.kind in {"source", "chunk"} else [],
                claim_ids=[hit.id] if hit.kind == "claim" else [],
                section_title=hit.section_title,
                page_start=hit.page_start,
                page_end=hit.page_end,
            )

    hits = sorted(candidates.values(), key=lambda item: item.score, reverse=True)[:k]
    return BrokerSearchResult(hits=hits, active_project_id=active_project_id)


def render_broker_block(hits: list[BrokerHit], *, max_tokens: int | None = None) -> str:
    if not hits:
        return ""
    header = "### Second Brain — research recall"
    footer = "Use sb_load(<id>, depth=1) to inspect a node or sb_search for more."
    rendered: list[str] = [header, ""]
    running = _approx_tokens(header) + _approx_tokens(footer)
    truncated = False
    for idx, hit in enumerate(hits, 1):
        lines = [f"{idx}. [{hit.id}] {hit.kind}: {hit.title} (score {hit.score:.2f})"]
        if hit.summary:
            lines.append(f"   {hit.summary.strip()}")
        for evidence in hit.evidence[:2]:
            detail = evidence.matched_field
            if evidence.section_title:
                detail += f", {evidence.section_title}"
            if evidence.page_start is not None:
                if evidence.page_end and evidence.page_end != evidence.page_start:
                    detail += f", pp.{evidence.page_start}-{evidence.page_end}"
                else:
                    detail += f", p.{evidence.page_start}"
            lines.append(f"   ◇ evidence: {evidence.id} ({evidence.kind}, {detail})")
        block = "\n".join(lines)
        cost = _approx_tokens(block)
        if max_tokens is not None and running + cost > max_tokens and idx > 1:
            truncated = True
            break
        rendered.append(block)
        running += cost
    rendered.append("")
    if truncated:
        rendered.append("(truncated by injection budget)")
    rendered.append(footer)
    return "\n".join(rendered)


def _search_center_fts(cfg: Config, *, query: str, k: int) -> list[dict[str, object]]:
    if not cfg.fts_path.exists():
        return []
    fts_query = _fts_query(query)
    if not fts_query:
        return []
    with FtsStore.open(cfg.fts_path) as store:
        rows = store.search_centers(fts_query, k=k)
    return [
        {"id": row[0], "kind": row[1], "score": row[2], "matched_field": row[3]}
        for row in rows
    ]


def _default_project_id(center_docs: list[tuple[object, CenterDocument, str]]) -> str | None:
    active_projects = [
        doc.id for _path, doc, _body in center_docs if isinstance(doc, ProjectFrontmatter) and doc.active
    ]
    if len(active_projects) == 1:
        return active_projects[0]
    return None


def _linked_center_index(center_docs: list[tuple[object, CenterDocument, str]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for _path, doc, _body in center_docs:
        linked = set(doc.source_ids) | set(doc.claim_ids) | set(doc.paper_ids) | set(doc.experiment_ids)
        for linked_id in linked:
            index.setdefault(linked_id, []).append(doc.id)
    return index


def _active_project_links(doc: CenterDocument | None) -> set[str]:
    if doc is None or doc.kind != CenterKind.PROJECT:
        return set()
    return set(doc.paper_ids) | set(doc.claim_ids) | set(doc.experiment_ids) | set(doc.synthesis_ids)


def _project_boost(
    doc: CenterDocument,
    active_project_id: str | None,
    active_project_links: set[str],
) -> float:
    if active_project_id and active_project_id in doc.project_ids:
        return 0.20
    if active_project_id and doc.id == active_project_id:
        return 0.35
    if doc.id in active_project_links:
        return 0.15
    return 0.0


def _title_for_side_hit(cfg: Config, hit: RetrievalHit) -> str:
    if hit.kind == "chunk":
        if hit.source_title and hit.section_title:
            return f"{hit.source_title} — {hit.section_title}"
        if hit.source_title:
            return hit.source_title
        if hit.section_title:
            return hit.section_title
        if hit.source_id:
            source_path = cfg.sources_dir / hit.source_id / "_source.md"
            if source_path.exists():
                meta, _body = load_document(source_path)
                return str(meta.get("title", hit.id))
        return hit.id
    if hit.kind == "claim":
        path = _claim_path(cfg, hit.id)
        if path and path.exists():
            meta, _body = load_document(path)
            return str(meta.get("statement", hit.id))
    if hit.kind == "source":
        path = cfg.sources_dir / hit.id / "_source.md"
        if path.exists():
            meta, _body = load_document(path)
            return str(meta.get("title", hit.id))
    return hit.id


def _summary_for_side_hit(cfg: Config, hit: RetrievalHit) -> str:
    if hit.kind == "chunk":
        return hit.snippet or _first_paragraph(hit.snippet)
    if hit.kind == "claim":
        path = _claim_path(cfg, hit.id)
        if path and path.exists():
            meta, body = load_document(path)
            return str(meta.get("abstract", "") or _first_paragraph(body))
    if hit.kind == "source":
        path = cfg.sources_dir / hit.id / "_source.md"
        if path.exists():
            meta, body = load_document(path)
            return str(meta.get("abstract", "") or _first_paragraph(body))
    return hit.snippet


def _claim_path(cfg: Config, claim_id: str):
    if not cfg.claims_dir.exists():
        return None
    for path in cfg.claims_dir.glob("*.md"):
        if path.parent.name == "resolutions":
            continue
        meta, _body = load_document(path)
        if meta.get("id") == claim_id:
            return path
    return None


def _first_paragraph(text: str) -> str:
    for para in text.split("\n\n"):
        compact = " ".join(para.split()).strip()
        if compact:
            return compact[:500]
    return ""


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _fts_query(query: str) -> str:
    tokens = [token.lower() for token in _TOKEN_RE.findall(query) if len(token) > 1]
    if not tokens:
        return query.strip()
    return " OR ".join(f'"{token}"' for token in tokens[:12])
