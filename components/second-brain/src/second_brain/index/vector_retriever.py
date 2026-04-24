"""Vector-based retriever over the sqlite-vec store.

Contract mirrors :class:`second_brain.index.retriever.BM25Retriever`:
returns a list of :class:`RetrievalHit` sorted by score descending, with
``matched_field="vector"`` so callers can tell which path produced a hit.
"""
from __future__ import annotations

from collections.abc import Callable

from second_brain.config import Config
from second_brain.embed.base import Embedder
from second_brain.index.retriever import RetrievalHit, Scope
from second_brain.index.vector_store import VectorStore
from second_brain.store.duckdb_store import DuckStore


def _default_embedder_factory(cfg: Config) -> Embedder:  # pragma: no cover - lazy path
    from second_brain.habits.loader import load_habits

    habits = load_habits(cfg)
    if habits.retrieval.embedding_model == "claude":
        from second_brain.embed.claude import ClaudeEmbedder

        return ClaudeEmbedder()
    from second_brain.embed.local import LocalEmbedder

    return LocalEmbedder()


class VectorRetriever:
    """Retriever that queries sqlite-vec via an injected Embedder."""

    def __init__(
        self,
        cfg: Config,
        *,
        embedder: Embedder | None = None,
        embedder_factory: Callable[[Config], Embedder] | None = None,
    ) -> None:
        self.cfg = cfg
        if embedder is not None:
            self._embedder: Embedder = embedder
        else:
            factory = embedder_factory or _default_embedder_factory
            self._embedder = factory(cfg)

    def search(
        self,
        query: str,
        k: int = 10,
        scope: Scope = "both",
        taxonomy: str | None = None,
        with_neighbors: bool = False,
        include_superseded: bool = False,
    ) -> list[RetrievalHit]:
        del taxonomy, with_neighbors, include_superseded
        stripped = query.strip()
        if not stripped:
            return []
        if not self.cfg.vectors_path.exists():
            return []

        embedding = self._embedder.embed([stripped])[0]
        raw: list[tuple[str, str, float]] = []  # (id, kind, distance)
        with VectorStore.open(self.cfg.vectors_path) as store:
            if scope in ("claims", "both"):
                for id_, dist in store.topk("claim", embedding, k=k):
                    raw.append((id_, "claim", dist))
            if scope in ("sources", "both"):
                for id_, dist in store.topk("chunk", embedding, k=k):
                    raw.append((id_, "chunk", dist))
                for id_, dist in store.topk("source", embedding, k=k):
                    raw.append((id_, "source", dist))

        # Lower distance → better. Convert to rank-normalized [0.3, 1.0] so
        # the hit score is comparable with BM25's normalized range.
        raw.sort(key=lambda r: r[2])
        raw = raw[:k]
        total = len(raw)
        hits: list[RetrievalHit] = []
        for rank, (id_, kind, _dist) in enumerate(raw):
            normalized = 1.0 - (0.7 * rank / max(total - 1, 1)) if total > 1 else 1.0
            source_id = None
            chunk_id = None
            section_title = ""
            page_start = None
            page_end = None
            if kind == "chunk":
                source_id, section_title, page_start, page_end = self._chunk_meta(id_)
                chunk_id = id_
            hits.append(
                RetrievalHit(
                    id=id_,
                    kind=kind,  # type: ignore[arg-type]
                    score=normalized,
                    matched_field="vector",
                    source_id=source_id,
                    chunk_id=chunk_id,
                    section_title=section_title,
                    page_start=page_start,
                    page_end=page_end,
                )
            )
        return hits

    def _chunk_meta(self, chunk_id: str) -> tuple[str | None, str, int | None, int | None]:
        if not self.cfg.duckdb_path.exists():
            return None, "", None, None
        with DuckStore.open(self.cfg.duckdb_path) as store:
            row = store.conn.execute(
                "SELECT source_id, section_title, page_start, page_end FROM chunks WHERE id = ?",
                [chunk_id],
            ).fetchone()
        if not row:
            return None, "", None, None
        return row[0], row[1] or "", row[2], row[3]
