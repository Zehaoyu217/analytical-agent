from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.graph.property_graph import create_property_graph
from second_brain.index.chunker import build_chunks, write_chunk_manifest
from second_brain.research.schema import iter_center_documents
from second_brain.schema.claim import ClaimFrontmatter
from second_brain.schema.edges import (
    CLAIM_TO_CLAIM,
    CLAIM_TO_SOURCE,
    SOURCE_TO_SOURCE,
    EdgeConfidence,
    RelationType,
)
from second_brain.schema.source import SourceFrontmatter
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore

if TYPE_CHECKING:  # pragma: no cover
    from second_brain.embed.base import Embedder

_log = logging.getLogger(__name__)


def reindex(
    cfg: Config,
    *,
    with_vectors: bool = False,
    embedder: Embedder | None = None,
    vector_batch_size: int = 32,
) -> None:
    """Deterministic: markdown → DuckDB + FTS5. Atomic swap to live paths."""
    staging_dir = cfg.sb_dir / "next"
    staging_dir.mkdir(parents=True, exist_ok=True)
    stg_duck = staging_dir / "graph.duckdb"
    stg_fts = staging_dir / "kb.sqlite"
    if stg_duck.exists():
        stg_duck.unlink()
    if stg_fts.exists():
        stg_fts.unlink()

    sources = list(_iter_sources(cfg.sources_dir))
    claims = list(_iter_claims(cfg.claims_dir))
    centers = list(iter_center_documents(cfg))
    chunks = []

    with DuckStore.open(stg_duck) as dstore, FtsStore.open(stg_fts) as fstore:
        dstore.ensure_schema()
        fstore.ensure_schema()

        for path, sf, body in sources:
            source_chunks = build_chunks(sf.id, body)
            write_chunk_manifest(path.parent / "chunk_manifest.json", source_chunks)
            chunks.extend(source_chunks)
            dstore.insert_source(
                id=sf.id,
                slug=path.parent.name,
                title=sf.title,
                kind=sf.kind.value,
                year=sf.year,
                habit_taxonomy=sf.habit_taxonomy,
                content_hash=sf.content_hash,
                abstract=sf.abstract,
                ingested_at=sf.ingested_at.isoformat(),
            )
            fstore.insert_source(
                source_id=sf.id,
                title=sf.title,
                abstract=sf.abstract,
                processed_body=body,
                taxonomy=sf.habit_taxonomy or "",
            )
            for chunk in source_chunks:
                dstore.insert_chunk(
                    id=chunk.id,
                    source_id=chunk.source_id,
                    ordinal=chunk.ordinal,
                    section_title=chunk.section_title,
                    body=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
                fstore.insert_chunk(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    source_title=sf.title,
                    section_title=chunk.section_title,
                    body=chunk.text,
                    taxonomy=sf.habit_taxonomy or "",
                    page_span=chunk.page_span,
                )
            _write_source_edges(dstore, sf, path)

        for path, cf, body in claims:
            dstore.insert_claim(
                id=cf.id,
                statement=cf.statement,
                body=body,
                abstract=cf.abstract,
                kind=cf.kind.value,
                confidence=cf.confidence.value,
                status=cf.status.value,
                resolution=cf.resolution,
            )
            fstore.insert_claim(
                claim_id=cf.id,
                statement=cf.statement,
                abstract=cf.abstract,
                body=body,
                taxonomy="",
            )
            _write_claim_edges(dstore, cf, path)

        for path, center, body in centers:
            dstore.insert_center_node(
                id=center.id,
                kind=center.kind.value,
                title=center.title,
                status=center.status.value,
                summary=center.summary,
                confidence=float(center.confidence),
                updated_at=center.updated_at.isoformat(),
            )
            fstore.insert_center(
                center_id=center.id,
                kind=center.kind.value,
                title=center.title,
                summary=center.summary,
                body=body,
                tags=" ".join(center.tags),
            )
            _write_center_edges(dstore, center, path)

    with DuckStore.open(stg_duck) as dstore:
        create_property_graph(dstore.conn)

    # FTS first so its file is out of staging_dir before DuckStore.atomic_swap
    # wipes the staging parent with shutil.rmtree.
    FtsStore.atomic_swap(staging=stg_fts, target=cfg.fts_path)
    DuckStore.atomic_swap(staging=stg_duck, target=cfg.duckdb_path)

    if with_vectors:
        _reindex_vectors(
            cfg,
            sources=sources,
            claims=claims,
            chunks=chunks,
            embedder=embedder,
            batch_size=vector_batch_size,
        )


def _reindex_vectors(
    cfg: Config,
    *,
    sources: list,
    claims: list,
    chunks: list,
    embedder: Embedder | None,
    batch_size: int,
) -> None:
    """Embed claim+source text and upsert into ``vectors.sqlite``.

    Resilient: each batch runs in its own try/except so one bad embedding
    call doesn't wipe out the whole reindex.
    """
    from second_brain.index.vector_store import VectorStore

    if embedder is None:
        from second_brain.habits.loader import load_habits

        habits = load_habits(cfg)
        if habits.retrieval.embedding_model == "claude":
            from second_brain.embed.claude import ClaudeEmbedder

            embedder = ClaudeEmbedder()
        else:
            from second_brain.embed.local import LocalEmbedder

            embedder = LocalEmbedder()

    claim_items: list[tuple[str, str]] = [
        (cf.id, _compose_claim_text(cf, body)) for _path, cf, body in claims
    ]
    source_items: list[tuple[str, str]] = [
        (sf.id, _compose_source_text(sf)) for _path, sf, _body in sources
    ]
    chunk_items: list[tuple[str, str]] = [(chunk.id, chunk.text) for chunk in chunks]

    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=embedder.dim)
        _upsert_in_batches(store, "claim", claim_items, embedder, batch_size)
        _upsert_in_batches(store, "source", source_items, embedder, batch_size)
        _upsert_in_batches(store, "chunk", chunk_items, embedder, batch_size)


def _compose_claim_text(cf: ClaimFrontmatter, body: str) -> str:
    parts = [cf.statement, cf.abstract or "", body or ""]
    return "\n\n".join(p for p in parts if p).strip()


def _compose_source_text(sf: SourceFrontmatter) -> str:
    parts = [sf.title or "", sf.abstract or ""]
    return "\n\n".join(p for p in parts if p).strip()


def _upsert_in_batches(
    store,
    kind: str,
    items: list[tuple[str, str]],
    embedder: Embedder,
    batch_size: int,
) -> None:
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        ids = [id_ for id_, _ in chunk]
        texts = [text for _, text in chunk]
        try:
            vectors = embedder.embed(texts)
        except Exception as exc:
            _log.warning("embed batch %s[%d:%d] failed: %s", kind, start, start + len(chunk), exc)
            continue
        for id_, vec in zip(ids, vectors, strict=True):
            try:
                store.upsert(kind, id_, vec)  # type: ignore[arg-type]
            except Exception as exc:
                _log.warning("upsert %s %s failed: %s", kind, id_, exc)


def _iter_sources(sources_dir: Path):
    if not sources_dir.exists():
        return
    for path in sorted(sources_dir.glob("*/_source.md")):
        meta, body = load_document(path)
        yield path, SourceFrontmatter.from_frontmatter_dict(meta), body


def _iter_claims(claims_dir: Path):
    if not claims_dir.exists():
        return
    for path in sorted(claims_dir.glob("*.md")):
        if path.parent.name == "resolutions":
            continue
        meta, body = load_document(path)
        yield path, ClaimFrontmatter.from_frontmatter_dict(meta), body


def _write_source_edges(store: DuckStore, sf: SourceFrontmatter, path: Path) -> None:
    rel_map = [
        (RelationType.CITES, sf.cites),
        (RelationType.RELATED, sf.related),
        (RelationType.SUPERSEDES, sf.supersedes),
    ]
    for rel, targets in rel_map:
        for target in targets:
            assert rel in SOURCE_TO_SOURCE
            store.insert_edge(
                src_id=sf.id,
                dst_id=target,
                relation=rel.value,
                confidence=EdgeConfidence.EXTRACTED.value,
                rationale=None,
                source_markdown=str(path),
            )


def _write_claim_edges(store: DuckStore, cf: ClaimFrontmatter, path: Path) -> None:
    for target in cf.supports:
        assert RelationType.SUPPORTS in CLAIM_TO_SOURCE
        store.insert_edge(
            src_id=cf.id, dst_id=target, relation=RelationType.SUPPORTS.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
        # materialize reverse evidenced_by
        store.insert_edge(
            src_id=target, dst_id=cf.id, relation=RelationType.EVIDENCED_BY.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
    for target in cf.contradicts:
        assert RelationType.CONTRADICTS in CLAIM_TO_CLAIM
        store.insert_edge(
            src_id=cf.id, dst_id=target, relation=RelationType.CONTRADICTS.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
    for target in cf.refines:
        store.insert_edge(
            src_id=cf.id, dst_id=target, relation=RelationType.REFINES.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )


def _write_center_edges(store: DuckStore, center, path: Path) -> None:
    rel_map = {
        RelationType.IN_PROJECT: getattr(center, "project_ids", []),
        RelationType.INFORMS_PAPER: getattr(center, "paper_ids", []),
        RelationType.TESTS_CLAIM: getattr(center, "claim_ids", []),
        RelationType.USES_SOURCE: getattr(center, "source_ids", []),
        RelationType.SYNTHESIZES: getattr(center, "synthesis_ids", []),
    }
    for relation, targets in rel_map.items():
        for target in targets:
            store.insert_edge(
                src_id=center.id,
                dst_id=target,
                relation=relation.value,
                confidence=EdgeConfidence.INFERRED.value,
                rationale=None,
                source_markdown=str(path),
            )
