from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from second_brain.config import Config
from second_brain.store.fts_store import FtsStore

Scope = Literal["claims", "sources", "both"]
Kind = Literal["claim", "source", "chunk"]

# Conservative stopword set — just enough to stop natural-language prompts
# from reducing to zero-hit AND queries in FTS5. Keep small so recall stays high.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "that", "the", "their", "to", "was", "what", "when", "where", "which",
    "who", "why", "will", "with", "you", "your", "about", "tell",
})
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _to_fts_query(query: str) -> str:
    """Turn a free-form prompt into an FTS5 OR-query.

    FTS5 MATCH treats whitespace as implicit AND; a natural prompt like
    "tell me about the knowledge graph" would therefore require every token
    to appear in a row. We tokenize, drop stopwords, quote each remaining
    term to escape FTS5 syntax characters, and OR them.

    If the input is already an FTS5 expression (contains ``"`` or uppercase
    boolean operators followed by a space), we pass it through unchanged so
    power users keep full control.
    """
    stripped = query.strip()
    if not stripped:
        return stripped
    if '"' in stripped or re.search(r"\b(AND|OR|NOT|NEAR)\b", stripped):
        return stripped
    tokens = [t for t in _TOKEN_RE.findall(stripped.lower()) if t not in _STOPWORDS and len(t) > 1]
    if not tokens:
        return stripped
    return " OR ".join(f'"{t}"' for t in tokens)


@dataclass(frozen=True)
class RetrievalHit:
    id: str
    kind: Kind
    score: float
    matched_field: str
    snippet: str = ""
    neighbors: list[str] = field(default_factory=list)
    source_id: str | None = None
    chunk_id: str | None = None
    section_title: str = ""
    source_title: str = ""
    page_start: int | None = None
    page_end: int | None = None
    # Populated for kind="claim": the full falsifiable statement (the
    # abstract is often just a 1-line summary, but the agent needs the
    # statement to cite faithfully) plus the `supports:` source ids lifted
    # from the claim frontmatter so it can reference the origin paper
    # without a second tool call.
    statement: str = ""
    supports: list[str] = field(default_factory=list)


class Retriever(Protocol):
    def search(
        self,
        query: str,
        k: int = 10,
        scope: Scope = "both",
        taxonomy: str | None = None,
        with_neighbors: bool = False,
        include_superseded: bool = False,
    ) -> list[RetrievalHit]: ...


class BM25Retriever:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def search(
        self,
        query: str,
        k: int = 10,
        scope: Scope = "both",
        taxonomy: str | None = None,
        with_neighbors: bool = False,
        include_superseded: bool = False,
    ) -> list[RetrievalHit]:
        fts_query = _to_fts_query(query)
        if not fts_query:
            return []
        hits: list[RetrievalHit] = []
        with FtsStore.open(self.cfg.fts_path) as store:
            if scope in ("sources", "both"):
                for (
                    chunk_id,
                    source_id,
                    source_title,
                    section_title,
                    page_span,
                    score,
                    snippet,
                ) in store.search_chunks(fts_query, k=k):
                    if taxonomy and not self._taxonomy_matches(store, chunk_id, taxonomy, kind="chunk"):
                        continue
                    page_start, page_end = _parse_page_span(page_span)
                    hits.append(
                        RetrievalHit(
                            id=chunk_id,
                            kind="chunk",
                            score=score,
                            matched_field=self._guess_matched_field(
                                store, chunk_id, query, kind="chunk"
                            ),
                            snippet=snippet or "",
                            source_id=source_id,
                            chunk_id=chunk_id,
                            section_title=section_title or "",
                            source_title=source_title or "",
                            page_start=page_start,
                            page_end=page_end,
                        )
                    )
                for sid, score in store.search_sources(fts_query, k=k):
                    if taxonomy and not self._taxonomy_matches(store, sid, taxonomy, kind="source"):
                        continue
                    hits.append(RetrievalHit(
                        id=sid, kind="source", score=score,
                        matched_field=self._guess_matched_field(store, sid, query, kind="source"),
                        snippet=self._snippet_for(store, sid, kind="source"),
                        source_id=sid,
                    ))
            if scope in ("claims", "both"):
                for cid, score in store.search_claims(fts_query, k=k):
                    statement, snippet = self._claim_fields(store, cid)
                    hits.append(RetrievalHit(
                        id=cid, kind="claim", score=score,
                        matched_field=self._guess_matched_field(store, cid, query, kind="claim"),
                        snippet=snippet,
                        statement=statement,
                        supports=self._claim_supports(cid),
                    ))
        hits.sort(key=lambda h: h.score, reverse=True)
        if not include_superseded:
            hits = [h for h in hits if not self._is_superseded(h)]
        hits = hits[:k]
        hits = [self._normalized(h, rank=i, total=len(hits)) for i, h in enumerate(hits)]
        if with_neighbors:
            hits = [self._with_neighbors(h) for h in hits]
        return hits

    def _is_superseded(self, hit: RetrievalHit) -> bool:
        """Return True when *hit* is a claim whose frontmatter has ``superseded_by``.

        Non-claim hits (sources, chunks) always return False — supersession
        is a claim-level concept. One disk read per hit, bounded by k; the
        frontmatter is tiny so this is fast enough for every turn.
        """
        if hit.kind != "claim":
            return False
        slug = hit.id[len("clm_"):] if hit.id.startswith("clm_") else hit.id
        for candidate in (slug, hit.id):
            path = self.cfg.claims_dir / f"{candidate}.md"
            if not path.exists():
                continue
            try:
                from second_brain.frontmatter import load_document  # noqa: PLC0415
                fm, _ = load_document(path)
            except Exception:  # noqa: BLE001
                return False
            return bool(fm.get("superseded_by"))
        return False

    @staticmethod
    def _normalized(hit: RetrievalHit, *, rank: int, total: int) -> RetrievalHit:
        """Normalize raw BM25 into a [0.3, 1.0] rank-based score.

        SQLite FTS5 BM25 magnitudes depend heavily on corpus size; tiny
        corpora produce near-zero values that would be filtered by habit
        thresholds. A rank-based score keeps relative order and gives callers
        a stable interpretable range."""
        if total <= 0:
            return hit
        # Top hit -> 1.0, worst hit -> 0.3, linear interpolation.
        normalized = 1.0 - (0.7 * rank / max(total - 1, 1)) if total > 1 else 1.0
        return RetrievalHit(
            id=hit.id, kind=hit.kind, score=normalized,
            matched_field=hit.matched_field,
            snippet=hit.snippet,
            neighbors=hit.neighbors,
            source_id=hit.source_id,
            chunk_id=hit.chunk_id,
            section_title=hit.section_title,
            source_title=hit.source_title,
            page_start=hit.page_start,
            page_end=hit.page_end,
            statement=hit.statement,
            supports=hit.supports,
        )

    def _taxonomy_matches(self, store: FtsStore, id: str, prefix: str, *, kind: Kind) -> bool:
        if kind == "source":
            table = "source_fts"
            col = "source_id"
        elif kind == "claim":
            table = "claim_fts"
            col = "claim_id"
        else:
            table = "chunk_fts"
            col = "chunk_id"
        row = store.conn.execute(
            f"SELECT taxonomy FROM {table} WHERE {col} = ?", (id,)
        ).fetchone()
        if not row:
            return False
        return (row[0] or "").startswith(prefix.rstrip("*").rstrip("/"))

    def _guess_matched_field(
        self, store: FtsStore, id: str, query: str, *, kind: Kind
    ) -> str:
        # Cheap heuristic: check which indexed column the query term appears in.
        if kind == "source":
            table = "source_fts"
            col = "source_id"
            fields = ["title", "abstract", "processed_body"]
        elif kind == "claim":
            table = "claim_fts"
            col = "claim_id"
            fields = ["statement", "abstract", "body"]
        else:
            table = "chunk_fts"
            col = "chunk_id"
            fields = ["source_title", "section_title", "body"]
        row = store.conn.execute(
            f"SELECT {', '.join(fields)} FROM {table} WHERE {col} = ?", (id,)
        ).fetchone()
        if not row:
            return fields[0]
        q_lower = query.lower()
        for field_name, value in zip(fields, row, strict=False):
            if value and q_lower in value.lower():
                return field_name
        return fields[0]

    def _claim_fields(self, store: FtsStore, cid: str) -> tuple[str, str]:
        """Return (statement, snippet) for *cid*.

        Used by the injection path so the agent sees the full atomic claim
        statement AND a short evidence snippet — the abstract alone often
        reads as a 1-line paraphrase without the precise assertion.
        """
        row = store.conn.execute(
            "SELECT statement, abstract, body FROM claim_fts WHERE claim_id = ?",
            (cid,),
        ).fetchone()
        if not row:
            return "", ""
        statement = " ".join((row[0] or "").split()).strip()
        snippet = _best_snippet(row[1], row[2], fallback=row[0] or "")
        return statement, snippet

    def _claim_supports(self, cid: str) -> list[str]:
        """Return the source ids the claim `supports:` — from the property graph.

        The FTS index doesn't carry edge metadata; the property-graph DuckDB
        does. When the file is absent (fresh install, tests) we return empty.
        """
        if not self.cfg.duckdb_path.exists():
            return []
        from second_brain.store.duckdb_store import DuckStore  # noqa: PLC0415
        with DuckStore.open(self.cfg.duckdb_path) as store:
            rows = store.conn.execute(
                "SELECT dst_id FROM edges WHERE src_id = ? AND relation = 'supports'",
                [cid],
            ).fetchall()
        return [str(r[0]) for r in rows]

    def _snippet_for(self, store: FtsStore, id: str, *, kind: Kind) -> str:
        if kind == "source":
            row = store.conn.execute(
                "SELECT abstract, processed_body FROM source_fts WHERE source_id = ?",
                (id,),
            ).fetchone()
            if not row:
                return ""
            return _best_snippet(row[0], row[1])
        if kind == "claim":
            row = store.conn.execute(
                "SELECT statement, abstract, body FROM claim_fts WHERE claim_id = ?",
                (id,),
            ).fetchone()
            if not row:
                return ""
            return _best_snippet(row[1], row[2], fallback=row[0])
        return ""

    def _with_neighbors(self, hit: RetrievalHit) -> RetrievalHit:
        from second_brain.store.duckdb_store import DuckStore
        ids: list[str] = []
        if hit.kind == "chunk" and hit.source_id:
            ids.append(hit.source_id)
        if not self.cfg.duckdb_path.exists():
            return hit
        with DuckStore.open(self.cfg.duckdb_path) as store:
            rows = store.conn.execute(
                "SELECT dst_id FROM edges WHERE src_id = ? "
                "UNION SELECT src_id FROM edges WHERE dst_id = ?",
                [hit.id, hit.id],
            ).fetchall()
        ids = [r[0] for r in rows]
        return RetrievalHit(
            id=hit.id, kind=hit.kind, score=hit.score,
            matched_field=hit.matched_field,
            snippet=hit.snippet,
            neighbors=ids,
            source_id=hit.source_id,
            statement=hit.statement,
            supports=hit.supports,
            chunk_id=hit.chunk_id,
            section_title=hit.section_title,
            source_title=hit.source_title,
            page_start=hit.page_start,
            page_end=hit.page_end,
        )


class HybridRetriever:
    """BM25 + VectorRetriever fused via Reciprocal Rank Fusion.

    Each underlying retriever is queried with ``k * OVERSAMPLE`` so the
    fused top-``k`` has enough candidates to pick from. Hits are labeled
    with ``matched_field="hybrid:bm25"``, ``"hybrid:vec"``, or
    ``"hybrid:both"`` depending on which list(s) contributed.
    """

    OVERSAMPLE = 3

    def __init__(
        self,
        cfg: Config,
        *,
        embedder: object | None = None,
    ) -> None:
        from second_brain.habits.loader import load_habits
        from second_brain.index.vector_retriever import VectorRetriever

        self.cfg = cfg
        self._bm25 = BM25Retriever(cfg)
        if embedder is not None:
            self._vector = VectorRetriever(cfg, embedder=embedder)  # type: ignore[arg-type]
        else:
            self._vector = VectorRetriever(cfg)
        self._rrf_k = load_habits(cfg).retrieval.rrf_k

    def search(
        self,
        query: str,
        k: int = 10,
        scope: Scope = "both",
        taxonomy: str | None = None,
        with_neighbors: bool = False,
        include_superseded: bool = False,
    ) -> list[RetrievalHit]:
        from second_brain.index.rrf import rrf_fuse

        oversample_k = k * self.OVERSAMPLE
        bm25_hits = self._bm25.search(
            query, k=oversample_k, scope=scope, taxonomy=taxonomy,
            include_superseded=include_superseded,
        )
        vec_hits = self._vector.search(query, k=oversample_k, scope=scope)

        by_id: dict[str, RetrievalHit] = {}
        for h in bm25_hits:
            by_id[h.id] = h
        for h in vec_hits:
            if h.id not in by_id:
                by_id[h.id] = h

        bm25_ids = [h.id for h in bm25_hits]
        vec_ids = [h.id for h in vec_hits]
        fused = rrf_fuse([bm25_ids, vec_ids], k_rrf=self._rrf_k)[:k]

        bm25_set = set(bm25_ids)
        vec_set = set(vec_ids)

        out: list[RetrievalHit] = []
        for id_, score in fused:
            base = by_id[id_]
            if id_ in bm25_set and id_ in vec_set:
                matched = "hybrid:both"
            elif id_ in bm25_set:
                matched = "hybrid:bm25"
            elif id_ in vec_set:
                matched = "hybrid:vec"
            else:  # pragma: no cover — rrf ids always originate from lists
                matched = "hybrid"
            out.append(
                RetrievalHit(
                    id=base.id,
                    kind=base.kind,
                    score=score,
                    matched_field=matched,
                    snippet=base.snippet,
                    neighbors=base.neighbors,
                    source_id=base.source_id,
                    chunk_id=base.chunk_id,
                    section_title=base.section_title,
                    source_title=base.source_title,
                    page_start=base.page_start,
                    page_end=base.page_end,
                )
            )
        if with_neighbors:
            out = [self._bm25._with_neighbors(h) for h in out]
        return out


def make_retriever(cfg: Config) -> Retriever:
    """Pick the right retriever based on habits + on-disk artifacts.

    Graceful degradation: even when ``habits.retrieval.mode == "hybrid"``,
    if ``.sb/vectors.sqlite`` is missing we fall back to BM25 so the search
    tool keeps working after a clean clone.
    """
    from second_brain.habits.loader import load_habits

    habits = load_habits(cfg)
    if habits.retrieval.mode == "hybrid" and cfg.vectors_path.exists():
        return HybridRetriever(cfg)
    return BM25Retriever(cfg)


def _best_snippet(primary: str | None, secondary: str | None, *, fallback: str = "") -> str:
    for candidate in (primary, secondary, fallback):
        text = " ".join((candidate or "").split()).strip()
        if text:
            return text[:280]
    return ""


def _parse_page_span(page_span: str) -> tuple[int | None, int | None]:
    raw = (page_span or "").strip()
    if not raw:
        return None, None
    single = re.match(r"^p\.(\d+)$", raw)
    if single:
        page = int(single.group(1))
        return page, page
    multi = re.match(r"^pp\.(\d+)-(\d+)$", raw)
    if multi:
        return int(multi.group(1)), int(multi.group(2))
    return None, None
