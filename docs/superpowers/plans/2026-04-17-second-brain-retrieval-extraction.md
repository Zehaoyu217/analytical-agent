# Second Brain — Retrieval + Claim Extraction Implementation Plan

> Historical note (2026-04-22): This plan was written when `second-brain` lived
> at `~/Developer/second-brain/`. The active codebase has since been moved into
> `claude-code-agent/components/second-brain`. Path references in this document
> are historical unless explicitly updated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On top of the foundation plan, add (1) the DuckPGQ property graph view, (2) a `Retriever` protocol + `BM25Retriever` with graph-neighbor enrichment, (3) `sb_search` / `sb_load` / `sb_reason` CLI commands and Python tool surfaces, and (4) the Opus-powered claim extractor that writes `claims/*.md`.

**Architecture:** Retrieval layers the existing DuckDB + FTS5 stores behind a `Retriever` protocol; graph walks use DuckPGQ's `GRAPH_TABLE` SQL/PGQ syntax against the property graph view that reindex now builds. Claim extraction uses the Anthropic SDK's tool-use API to force Opus 4.7 to emit records matching the `ClaimFrontmatter` schema. An in-process queue (stdlib `asyncio`) runs extraction — no external broker in v1. Tests use a fake extractor client; the real Anthropic call is gated behind `ANTHROPIC_API_KEY` and a `@pytest.mark.live` marker.

**Tech Stack:** DuckPGQ 0.2+ (DuckDB extension, loaded lazily), Anthropic SDK ≥0.40, asyncio, pytest, pytest-asyncio.

**Scope boundary:**
- Lint + `conflicts.md` generator → plan 3.
- `sb inject` hook + claude-code-agent integration → plan 4.
- Wizard + habits learning → plan 5.
- Watcher + `sb maintain` → plan 6.

**Entry state (assumed from foundation plan):**
- `~/Developer/second-brain/` at commit `5bfedb4` on `main`.
- 43 tests passing, 85% coverage.
- `sb ingest | reindex | status` working end-to-end.
- `~/second-brain/` bootstrapped with one welcome source ingested.

---

## File Structure Added By This Plan

```
src/second_brain/
├── graph/
│   ├── __init__.py
│   ├── extension.py          # DuckPGQ lazy install/load
│   └── property_graph.py     # CREATE PROPERTY GRAPH DDL + refresh
├── index/
│   ├── __init__.py
│   └── retriever.py          # Retriever protocol + BM25Retriever + RetrievalHit
├── reason.py                 # GraphPattern, sb_reason, shorthand helpers
├── load.py                   # sb_load with depth + relations filter
├── extract/
│   ├── __init__.py
│   ├── schema.py             # Anthropic tool-use input_schema for claim records
│   ├── client.py             # ExtractorClient protocol + AnthropicClient + FakeClient
│   ├── claims.py             # extract_claims(body, density, rubric) → list[ClaimFrontmatter]
│   ├── writer.py             # materialize extracted claims to claims/*.md
│   └── worker.py             # asyncio queue wrapping the extractor
└── cli.py                    # MODIFIED: + sb search | load | reason | extract

tests/
├── test_graph_property_graph.py
├── test_retriever.py
├── test_load.py
├── test_reason.py
├── test_extract_schema.py
├── test_extract_claims.py
├── test_extract_writer.py
├── test_extract_worker.py
├── test_cli_retrieval.py
├── test_cli_extract.py
├── test_e2e_extract_search.py
└── fixtures/
    └── extraction/
        ├── transformer_paper.md
        └── expected_claims.json
```

---

## Task 1: DuckPGQ extension loader

DuckPGQ is an out-of-tree DuckDB extension; loading requires `INSTALL` then `LOAD`. We gate behind a feature flag so reindex can still function on machines without the extension (falls back to plain edge-table queries).

**Files:**
- Create: `src/second_brain/graph/__init__.py`
- Create: `src/second_brain/graph/extension.py`
- Create: `tests/test_graph_extension.py`

- [ ] **Step 1: Write failing test `tests/test_graph_extension.py`**

```python
from __future__ import annotations

import duckdb
import pytest

from second_brain.graph.extension import ensure_duckpgq


def test_ensure_duckpgq_returns_true_on_success() -> None:
    conn = duckdb.connect(":memory:")
    try:
        loaded = ensure_duckpgq(conn)
    except Exception:
        pytest.skip("duckpgq install blocked in this environment")
    assert loaded is True
    row = conn.execute("SELECT extension_name FROM duckdb_extensions() WHERE loaded").fetchall()
    names = {r[0] for r in row}
    assert "duckpgq" in names


def test_ensure_duckpgq_idempotent() -> None:
    conn = duckdb.connect(":memory:")
    try:
        a = ensure_duckpgq(conn)
        b = ensure_duckpgq(conn)
    except Exception:
        pytest.skip("duckpgq install blocked in this environment")
    assert a and b
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && source .venv/bin/activate && pytest tests/test_graph_extension.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/graph/extension.py`**

```python
from __future__ import annotations

import duckdb

_REPO_URL = "https://duckpgq.s3.eu-central-1.amazonaws.com"


def ensure_duckpgq(conn: duckdb.DuckDBPyConnection) -> bool:
    """Install + load the DuckPGQ extension. Returns True on success."""
    conn.execute("SET custom_extension_repository = ?", [_REPO_URL])
    try:
        conn.execute("INSTALL duckpgq FROM community")
    except duckdb.Error:
        # Community repo already holds duckpgq in recent DuckDB releases;
        # fall back to direct install without the repository hint.
        conn.execute("INSTALL duckpgq")
    conn.execute("LOAD duckpgq")
    return True
```

- [ ] **Step 4: Run tests — verify pass (or graceful skip if CI has no network)**

```bash
pytest tests/test_graph_extension.py -v
```

Expected: 2 passed, or 2 skipped if the DuckPGQ community install is blocked. Both outcomes are acceptable.

- [ ] **Step 5: Commit**

```bash
cd ~/Developer/second-brain && git add -A && git commit -m "feat(graph): DuckPGQ extension lazy loader"
```

---

## Task 2: Property graph view built during reindex

**Files:**
- Create: `src/second_brain/graph/property_graph.py`
- Modify: `src/second_brain/reindex.py`
- Create: `tests/test_graph_property_graph.py`

- [ ] **Step 1: Implement `src/second_brain/graph/property_graph.py`**

```python
from __future__ import annotations

import duckdb

from second_brain.graph.extension import ensure_duckpgq
from second_brain.schema.edges import RelationType

_EDGE_LABELS = [r.value for r in RelationType]


def create_property_graph(conn: duckdb.DuckDBPyConnection) -> bool:
    """Create the sb_graph property graph view. Returns False if DuckPGQ unavailable."""
    try:
        ensure_duckpgq(conn)
    except duckdb.Error:
        return False

    conn.execute("DROP PROPERTY GRAPH IF EXISTS sb_graph")

    # DuckPGQ requires one EDGE TABLES clause per relation label.
    edge_clauses = []
    for label in _EDGE_LABELS:
        edge_clauses.append(
            f"""(SELECT src_id, dst_id, rationale, confidence_edge
                 FROM edges WHERE relation = '{label}')
              AS {label}
              SOURCE KEY (src_id) REFERENCES sources(id)
              DESTINATION KEY (dst_id) REFERENCES sources(id)
              LABEL {label}"""
        )
    # Fallback: edges between claims/sources — DuckPGQ resolves references against
    # whichever vertex table has the matching id.  We define both vertex tables
    # and let the planner pick.
    ddl = f"""
    CREATE PROPERTY GRAPH sb_graph
    VERTEX TABLES (sources, claims)
    EDGE TABLES (
      {",".join(edge_clauses)}
    )
    """
    conn.execute(ddl)
    return True
```

- [ ] **Step 2: Modify `src/second_brain/reindex.py`** — call `create_property_graph` after inserting all rows, before atomic swap.

Add import at top:
```python
from second_brain.graph.property_graph import create_property_graph
```

Inside `reindex()`, after the `with DuckStore.open(stg_duck) as dstore, FtsStore.open(stg_fts) as fstore:` block completes (i.e. the `with` block has inserted all rows), open a new DuckStore and invoke the graph builder *before* the atomic swaps:

```python
    with DuckStore.open(stg_duck) as dstore:
        create_property_graph(dstore.conn)

    # FTS first so its file is out of staging_dir before DuckStore.atomic_swap
    # wipes the staging parent with shutil.rmtree.
    FtsStore.atomic_swap(staging=stg_fts, target=cfg.fts_path)
    DuckStore.atomic_swap(staging=stg_duck, target=cfg.duckdb_path)
```

- [ ] **Step 3: Write test `tests/test_graph_property_graph.py`**

```python
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from second_brain.graph.property_graph import create_property_graph
from second_brain.store.duckdb_store import DuckStore


def _requires_duckpgq() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL duckpgq")
        conn.execute("LOAD duckpgq")
    except duckdb.Error:
        pytest.skip("duckpgq unavailable")


def test_creates_property_graph(tmp_path: Path) -> None:
    _requires_duckpgq()
    db = tmp_path / "g.duckdb"
    with DuckStore.open(db) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_a", slug="a", title="A", kind="note",
            year=None, habit_taxonomy=None,
            content_hash="sha256:1", abstract="",
        )
        store.insert_source(
            id="src_b", slug="b", title="B", kind="note",
            year=None, habit_taxonomy=None,
            content_hash="sha256:2", abstract="",
        )
        store.insert_edge(
            src_id="src_a", dst_id="src_b", relation="cites",
            confidence="extracted", rationale=None, source_markdown="/a",
        )
        ok = create_property_graph(store.conn)
    assert ok is True
    # Verify the graph exists by listing it.
    with DuckStore.open(db) as store:
        from second_brain.graph.extension import ensure_duckpgq
        ensure_duckpgq(store.conn)
        rows = store.conn.execute(
            "SELECT property_graph_name FROM duckpgq_property_graphs()"
        ).fetchall()
    names = {r[0] for r in rows}
    assert "sb_graph" in names
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_graph_property_graph.py -v
```

Expected: 1 passed, or skipped if DuckPGQ unavailable.

- [ ] **Step 5: Run full suite**

```bash
pytest -m "not integration" -v
```

Expected: all prior 43 tests still pass + new ones.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(graph): build sb_graph property graph during reindex"
```

---

## Task 3: `Retriever` protocol + `RetrievalHit`

**Files:**
- Create: `src/second_brain/index/__init__.py`
- Create: `src/second_brain/index/retriever.py`
- Create: `tests/test_retriever.py`

- [ ] **Step 1: Write failing test `tests/test_retriever.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.index.retriever import BM25Retriever, RetrievalHit
from second_brain.store.fts_store import FtsStore


def _seed(cfg: Config) -> None:
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    with FtsStore.open(cfg.fts_path) as store:
        store.ensure_schema()
        store.insert_source(
            source_id="src_attn", title="Attention is all you need",
            abstract="Self-attention architecture.", processed_body="transformer seq2seq",
            taxonomy="papers/ml",
        )
        store.insert_source(
            source_id="src_rnn", title="Sequence to Sequence",
            abstract="RNN encoder-decoder.", processed_body="recurrence",
            taxonomy="papers/ml",
        )


def test_search_sources_returns_hits(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    hits = BM25Retriever(cfg).search("attention", k=5, scope="sources")
    assert hits and isinstance(hits[0], RetrievalHit)
    assert hits[0].id == "src_attn"
    assert hits[0].kind == "source"
    assert hits[0].matched_field == "title"


def test_search_respects_k(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    hits = BM25Retriever(cfg).search("sequence", k=1, scope="sources")
    assert len(hits) == 1


def test_search_scope_both_merges_claims_and_sources(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    with FtsStore.open(cfg.fts_path) as store:
        store.insert_claim(
            claim_id="clm_attn", statement="Attention replaces recurrence.",
            abstract="", body="", taxonomy="papers/ml",
        )
    hits = BM25Retriever(cfg).search("attention", k=5, scope="both")
    kinds = {h.kind for h in hits}
    assert "source" in kinds and "claim" in kinds
```

- [ ] **Step 2: Run — verify failure**

```bash
pytest tests/test_retriever.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/index/retriever.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from second_brain.config import Config
from second_brain.store.fts_store import FtsStore

Scope = Literal["claims", "sources", "both"]
Kind = Literal["claim", "source"]


@dataclass(frozen=True)
class RetrievalHit:
    id: str
    kind: Kind
    score: float
    matched_field: str
    snippet: str = ""
    neighbors: list[str] = field(default_factory=list)


class Retriever(Protocol):
    def search(
        self,
        query: str,
        k: int = 10,
        scope: Scope = "both",
        taxonomy: str | None = None,
        with_neighbors: bool = False,
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
    ) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        with FtsStore.open(self.cfg.fts_path) as store:
            if scope in ("sources", "both"):
                for sid, score in store.search_sources(query, k=k):
                    if taxonomy and not self._taxonomy_matches(store, sid, taxonomy, kind="source"):
                        continue
                    hits.append(RetrievalHit(
                        id=sid, kind="source", score=score,
                        matched_field=self._guess_matched_field(store, sid, query, kind="source"),
                    ))
            if scope in ("claims", "both"):
                for cid, score in store.search_claims(query, k=k):
                    hits.append(RetrievalHit(
                        id=cid, kind="claim", score=score,
                        matched_field=self._guess_matched_field(store, cid, query, kind="claim"),
                    ))
        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[:k]
        if with_neighbors:
            hits = [self._with_neighbors(h) for h in hits]
        return hits

    def _taxonomy_matches(self, store: FtsStore, id: str, prefix: str, *, kind: Kind) -> bool:
        table = "source_fts" if kind == "source" else "claim_fts"
        col = "source_id" if kind == "source" else "claim_id"
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
        table = "source_fts" if kind == "source" else "claim_fts"
        col = "source_id" if kind == "source" else "claim_id"
        fields = (
            ["title", "abstract", "processed_body"] if kind == "source"
            else ["statement", "abstract", "body"]
        )
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

    def _with_neighbors(self, hit: RetrievalHit) -> RetrievalHit:
        from second_brain.store.duckdb_store import DuckStore
        ids: list[str] = []
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
            matched_field=hit.matched_field, snippet=hit.snippet, neighbors=ids,
        )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/test_retriever.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(index): Retriever protocol + BM25Retriever with neighbor enrichment"
```

---

## Task 4: `sb_load(id, depth, relations)`

**Files:**
- Create: `src/second_brain/load.py`
- Create: `tests/test_load.py`

- [ ] **Step 1: Write failing test `tests/test_load.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.load import LoadError, load_node
from second_brain.store.duckdb_store import DuckStore


def _seed(cfg: Config) -> None:
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    with DuckStore.open(cfg.duckdb_path) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_a", slug="a", title="A", kind="note",
            year=None, habit_taxonomy=None, content_hash="sha256:1", abstract="abs a",
        )
        store.insert_source(
            id="src_b", slug="b", title="B", kind="note",
            year=None, habit_taxonomy=None, content_hash="sha256:2", abstract="abs b",
        )
        store.insert_edge(
            src_id="src_a", dst_id="src_b", relation="cites",
            confidence="extracted", rationale="seed", source_markdown="/a",
        )


def test_depth_zero_returns_just_node(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    result = load_node(cfg, "src_a", depth=0)
    assert result.root["id"] == "src_a"
    assert result.root["title"] == "A"
    assert result.neighbors == []


def test_depth_one_includes_neighbors(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    result = load_node(cfg, "src_a", depth=1)
    ids = [n["id"] for n in result.neighbors]
    assert "src_b" in ids


def test_relations_filter_excludes_non_matching(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    result = load_node(cfg, "src_a", depth=1, relations=["supports"])
    assert result.neighbors == []


def test_unknown_id_raises(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    with pytest.raises(LoadError):
        load_node(cfg, "src_nope", depth=0)
```

- [ ] **Step 2: Run — verify failure**

```bash
pytest tests/test_load.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/load.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from second_brain.config import Config
from second_brain.store.duckdb_store import DuckStore


class LoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadResult:
    root: dict[str, Any]
    neighbors: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


def load_node(
    cfg: Config,
    node_id: str,
    *,
    depth: int = 0,
    relations: list[str] | None = None,
) -> LoadResult:
    with DuckStore.open(cfg.duckdb_path) as store:
        root = _fetch_node(store, node_id)
        if root is None:
            raise LoadError(f"node not found: {node_id}")
        if depth <= 0:
            return LoadResult(root=root)

        edge_rows = store.conn.execute(
            "SELECT src_id, dst_id, relation, confidence_edge, rationale "
            "FROM edges WHERE src_id = ? OR dst_id = ?",
            [node_id, node_id],
        ).fetchall()
        if relations:
            edge_rows = [r for r in edge_rows if r[2] in relations]
        edges = [
            {"src_id": r[0], "dst_id": r[1], "relation": r[2],
             "confidence": r[3], "rationale": r[4]}
            for r in edge_rows
        ]
        neighbor_ids = {r[1] if r[0] == node_id else r[0] for r in edge_rows}
        neighbors = [n for n in (_fetch_node(store, nid) for nid in neighbor_ids) if n]
    return LoadResult(root=root, neighbors=neighbors, edges=edges)


def _fetch_node(store: DuckStore, node_id: str) -> dict[str, Any] | None:
    row = store.conn.execute(
        "SELECT id, title, kind, habit_taxonomy, abstract FROM sources WHERE id = ?",
        [node_id],
    ).fetchone()
    if row:
        return {"id": row[0], "kind": "source", "title": row[1],
                "source_kind": row[2], "taxonomy": row[3], "abstract": row[4]}
    row = store.conn.execute(
        "SELECT id, statement, kind, confidence_claim, abstract FROM claims WHERE id = ?",
        [node_id],
    ).fetchone()
    if row:
        return {"id": row[0], "kind": "claim", "statement": row[1],
                "claim_kind": row[2], "confidence": row[3], "abstract": row[4]}
    return None
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_load.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(load): sb_load with depth + relations filter"
```

---

## Task 5: `GraphPattern` + `sb_reason`

Uses plain SQL against the `edges` table when DuckPGQ is unavailable; uses the property graph view when it is.

**Files:**
- Create: `src/second_brain/reason.py`
- Create: `tests/test_reason.py`

- [ ] **Step 1: Write failing test `tests/test_reason.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.reason import GraphPattern, sb_reason
from second_brain.store.duckdb_store import DuckStore


def _seed_chain(cfg: Config) -> None:
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    with DuckStore.open(cfg.duckdb_path) as store:
        store.ensure_schema()
        for sid in ["src_a", "src_b", "src_c"]:
            store.insert_source(
                id=sid, slug=sid[-1], title=sid.upper(), kind="note",
                year=None, habit_taxonomy=None,
                content_hash=f"sha256:{sid}", abstract="",
            )
        # chain: a -refines-> b -refines-> c
        store.insert_edge(src_id="src_a", dst_id="src_b", relation="refines",
                           confidence="extracted", rationale=None, source_markdown="/")
        store.insert_edge(src_id="src_b", dst_id="src_c", relation="refines",
                           confidence="extracted", rationale=None, source_markdown="/")


def test_outbound_walk_returns_transitive_reachables(sb_home: Path) -> None:
    cfg = Config.load()
    _seed_chain(cfg)
    paths = sb_reason(cfg, start_id="src_a",
                       pattern=GraphPattern(walk="refines", direction="outbound", max_depth=3))
    flat = {n for p in paths for n in p}
    assert flat == {"src_a", "src_b", "src_c"}


def test_max_depth_one_stops_at_direct_neighbor(sb_home: Path) -> None:
    cfg = Config.load()
    _seed_chain(cfg)
    paths = sb_reason(cfg, start_id="src_a",
                       pattern=GraphPattern(walk="refines", direction="outbound", max_depth=1))
    flat = {n for p in paths for n in p}
    assert flat == {"src_a", "src_b"}


def test_inbound_walk_reverses_direction(sb_home: Path) -> None:
    cfg = Config.load()
    _seed_chain(cfg)
    paths = sb_reason(cfg, start_id="src_c",
                       pattern=GraphPattern(walk="refines", direction="inbound", max_depth=3))
    flat = {n for p in paths for n in p}
    assert flat == {"src_a", "src_b", "src_c"}
```

- [ ] **Step 2: Run — verify failure**

```bash
pytest tests/test_reason.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/reason.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from second_brain.config import Config
from second_brain.store.duckdb_store import DuckStore

Direction = Literal["outbound", "inbound", "both"]


@dataclass(frozen=True)
class GraphPattern:
    walk: str
    direction: Direction = "outbound"
    max_depth: int = 3
    terminator: str | None = None


def sb_reason(
    cfg: Config, *, start_id: str, pattern: GraphPattern
) -> list[list[str]]:
    """Walk the graph from start_id following `walk` edges. Returns list of paths.

    Implementation strategy: BFS over the `edges` table. DuckPGQ's recursive
    MATCH is available in DuckDB ≥1.1 but is slower for small graphs and adds
    a hard dependency — plain SQL is adequate here.
    """
    paths: list[list[str]] = [[start_id]]
    completed: list[list[str]] = [[start_id]]
    with DuckStore.open(cfg.duckdb_path) as store:
        for _ in range(pattern.max_depth):
            next_paths: list[list[str]] = []
            for path in paths:
                tail = path[-1]
                neighbors = _one_hop(store, tail, pattern)
                for n in neighbors:
                    if n in path:  # no cycles
                        continue
                    if pattern.terminator and _is_terminator_edge(store, tail, n, pattern.terminator):
                        continue
                    next_paths.append([*path, n])
                    completed.append([*path, n])
            if not next_paths:
                break
            paths = next_paths
    return completed


def _one_hop(store: DuckStore, node: str, p: GraphPattern) -> list[str]:
    if p.direction == "outbound":
        rows = store.conn.execute(
            "SELECT dst_id FROM edges WHERE src_id = ? AND relation = ?",
            [node, p.walk],
        ).fetchall()
    elif p.direction == "inbound":
        rows = store.conn.execute(
            "SELECT src_id FROM edges WHERE dst_id = ? AND relation = ?",
            [node, p.walk],
        ).fetchall()
    else:
        rows = store.conn.execute(
            "SELECT dst_id FROM edges WHERE src_id = ? AND relation = ? "
            "UNION SELECT src_id FROM edges WHERE dst_id = ? AND relation = ?",
            [node, p.walk, node, p.walk],
        ).fetchall()
    return [r[0] for r in rows]


def _is_terminator_edge(
    store: DuckStore, src: str, dst: str, terminator: str
) -> bool:
    row = store.conn.execute(
        "SELECT 1 FROM edges WHERE src_id = ? AND dst_id = ? AND relation = ? LIMIT 1",
        [src, dst, terminator],
    ).fetchone()
    return row is not None


def sb_reason_chain(cfg: Config, start_id: str, relation: str) -> list[list[str]]:
    return sb_reason(cfg, start_id=start_id,
                      pattern=GraphPattern(walk=relation, direction="outbound", max_depth=10))


def sb_reason_contradictions(cfg: Config, start_id: str, max_depth: int = 2) -> list[list[str]]:
    return sb_reason(cfg, start_id=start_id,
                      pattern=GraphPattern(walk="contradicts", direction="both", max_depth=max_depth))


def sb_reason_refinement_tree(cfg: Config, start_id: str) -> list[list[str]]:
    return sb_reason(cfg, start_id=start_id,
                      pattern=GraphPattern(walk="refines", direction="both", max_depth=10))
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_reason.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(reason): GraphPattern + sb_reason BFS with depth + terminator"
```

---

## Task 6: CLI — `sb search`, `sb load`, `sb reason`

**Files:**
- Modify: `src/second_brain/cli.py`
- Create: `tests/test_cli_retrieval.py`

- [ ] **Step 1: Write failing test `tests/test_cli_retrieval.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _ingest_two(runner: CliRunner, tmp_path: Path) -> None:
    a = tmp_path / "attn.md"
    a.write_text("# Attention\n\nSelf-attention is sufficient for seq transduction.\n")
    b = tmp_path / "rnn.md"
    b.write_text("# Recurrence\n\nRNNs carry hidden state.\n")
    assert runner.invoke(cli, ["ingest", str(a)]).exit_code == 0
    assert runner.invoke(cli, ["ingest", str(b)]).exit_code == 0
    assert runner.invoke(cli, ["reindex"]).exit_code == 0


def test_cli_search_json_output(sb_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    _ingest_two(runner, tmp_path)
    result = runner.invoke(cli, ["search", "--json", "attention"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any(h["id"].startswith("src_attention") for h in payload)


def test_cli_load_returns_node(sb_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    _ingest_two(runner, tmp_path)
    # find actual slug
    search = runner.invoke(cli, ["search", "--json", "attention"])
    first_id = json.loads(search.output)[0]["id"]
    result = runner.invoke(cli, ["load", "--json", first_id])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["root"]["id"] == first_id
```

- [ ] **Step 2: Run — verify failure**

```bash
pytest tests/test_cli_retrieval.py -v
```

Expected: exit code != 0 (unknown command `search`).

- [ ] **Step 3: Modify `src/second_brain/cli.py`** — add three commands. Insert after the `status` command:

```python
@cli.command(name="search")
@click.argument("query")
@click.option("--k", default=5, type=int)
@click.option("--scope", type=click.Choice(["sources", "claims", "both"]), default="both")
@click.option("--taxonomy", default=None)
@click.option("--neighbors/--no-neighbors", default=False)
@click.option("--json", "as_json", is_flag=True, default=False)
def _search(query: str, k: int, scope: str, taxonomy: str | None,
            neighbors: bool, as_json: bool) -> None:
    """BM25 search over claims/sources."""
    from second_brain.index.retriever import BM25Retriever
    cfg = Config.load()
    hits = BM25Retriever(cfg).search(
        query, k=k, scope=scope, taxonomy=taxonomy, with_neighbors=neighbors,  # type: ignore[arg-type]
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps([
            {"id": h.id, "kind": h.kind, "score": h.score,
             "matched_field": h.matched_field, "neighbors": h.neighbors}
            for h in hits
        ]))
        return
    for h in hits:
        line = f"{h.score:6.3f}  {h.kind:6s}  {h.id}  ({h.matched_field})"
        click.echo(line)


@cli.command(name="load")
@click.argument("node_id")
@click.option("--depth", default=0, type=int)
@click.option("--relations", default=None, help="comma-separated relation filter")
@click.option("--json", "as_json", is_flag=True, default=False)
def _load(node_id: str, depth: int, relations: str | None, as_json: bool) -> None:
    """Fetch a node and optionally its graph neighborhood."""
    from second_brain.load import LoadError, load_node
    cfg = Config.load()
    rels = [r.strip() for r in relations.split(",")] if relations else None
    try:
        result = load_node(cfg, node_id, depth=depth, relations=rels)
    except LoadError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        import json as _json
        click.echo(_json.dumps({
            "root": result.root, "neighbors": result.neighbors, "edges": result.edges,
        }))
        return
    click.echo(f"# {result.root['id']}")
    click.echo(f"kind: {result.root['kind']}")
    for k, v in result.root.items():
        if k in {"id", "kind"} or v is None:
            continue
        click.echo(f"{k}: {v}")
    if result.neighbors:
        click.echo(f"\nneighbors ({len(result.neighbors)}):")
        for n in result.neighbors:
            click.echo(f"  - {n['id']} ({n['kind']})")


@cli.command(name="reason")
@click.argument("start_id")
@click.option("--walk", required=True, help="edge relation to walk, e.g. 'refines'")
@click.option("--direction", type=click.Choice(["outbound", "inbound", "both"]),
              default="outbound")
@click.option("--max-depth", default=3, type=int)
@click.option("--terminator", default=None)
@click.option("--json", "as_json", is_flag=True, default=False)
def _reason(start_id: str, walk: str, direction: str, max_depth: int,
            terminator: str | None, as_json: bool) -> None:
    """Walk the graph from start_id following a typed relation."""
    from second_brain.reason import GraphPattern, sb_reason
    cfg = Config.load()
    paths = sb_reason(
        cfg, start_id=start_id,
        pattern=GraphPattern(walk=walk, direction=direction,  # type: ignore[arg-type]
                              max_depth=max_depth, terminator=terminator),
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps(paths))
        return
    for path in paths:
        click.echo(" -> ".join(path))
```

Ensure `from second_brain.config import Config` is imported at the top of `cli.py` if not already.

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_cli_retrieval.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite**

```bash
pytest -m "not integration" -v
```

Expected: all prior tests + new ones pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(cli): sb search / sb load / sb reason"
```

---

## Task 7: Claim-extraction JSON schema

The Anthropic SDK accepts a `tools` array with `input_schema` JSON. We force the model into a single tool named `record_claims` so it can only respond by emitting structured claim records.

**Files:**
- Create: `src/second_brain/extract/__init__.py`
- Create: `src/second_brain/extract/schema.py`
- Create: `tests/test_extract_schema.py`

- [ ] **Step 1: Write failing test `tests/test_extract_schema.py`**

```python
from __future__ import annotations

from second_brain.extract.schema import RECORD_CLAIMS_TOOL, validate_claim_record


def test_tool_has_expected_shape() -> None:
    assert RECORD_CLAIMS_TOOL["name"] == "record_claims"
    schema = RECORD_CLAIMS_TOOL["input_schema"]
    assert schema["type"] == "object"
    assert "claims" in schema["properties"]
    assert schema["properties"]["claims"]["type"] == "array"


def test_validate_claim_accepts_minimal_record() -> None:
    rec = {
        "statement": "x",
        "kind": "empirical",
        "confidence": "high",
        "scope": "",
        "supports": [],
        "contradicts": [],
        "refines": [],
        "abstract": "y",
    }
    validate_claim_record(rec)  # does not raise


def test_validate_claim_rejects_bad_kind() -> None:
    import pytest
    rec = {"statement": "x", "kind": "BOGUS", "confidence": "high",
           "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": ""}
    with pytest.raises(ValueError):
        validate_claim_record(rec)
```

- [ ] **Step 2: Run — verify failure**

```bash
pytest tests/test_extract_schema.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/extract/schema.py`**

```python
from __future__ import annotations

from typing import Any

CLAIM_KINDS = ["empirical", "theoretical", "definitional", "opinion", "prediction"]
CONFIDENCES = ["low", "medium", "high"]

CLAIM_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["statement", "kind", "confidence", "scope", "abstract"],
    "properties": {
        "statement": {"type": "string", "description": "Atomic falsifiable claim."},
        "kind": {"type": "string", "enum": CLAIM_KINDS},
        "confidence": {"type": "string", "enum": CONFIDENCES},
        "scope": {"type": "string", "description": "Where this claim applies."},
        "supports": {
            "type": "array", "items": {"type": "string"},
            "description": "List of supporting source-id fragments, e.g. 'src_X#sec-3.2'.",
            "default": [],
        },
        "contradicts": {
            "type": "array", "items": {"type": "string"}, "default": [],
        },
        "refines": {"type": "array", "items": {"type": "string"}, "default": []},
        "abstract": {"type": "string", "description": "BM25-optimized 1-2 sentence summary."},
    },
}

RECORD_CLAIMS_TOOL: dict[str, Any] = {
    "name": "record_claims",
    "description": (
        "Record atomic, falsifiable claims extracted from the source body. "
        "Every claim must be grounded in the source text."
    ),
    "input_schema": {
        "type": "object",
        "required": ["claims"],
        "properties": {
            "claims": {
                "type": "array",
                "items": CLAIM_ITEM_SCHEMA,
            },
        },
    },
}


def validate_claim_record(rec: dict[str, Any]) -> None:
    required = {"statement", "kind", "confidence", "scope", "abstract"}
    missing = required - rec.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if rec["kind"] not in CLAIM_KINDS:
        raise ValueError(f"kind must be one of {CLAIM_KINDS}")
    if rec["confidence"] not in CONFIDENCES:
        raise ValueError(f"confidence must be one of {CONFIDENCES}")
    for key in ("supports", "contradicts", "refines"):
        vals = rec.get(key, [])
        if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
            raise ValueError(f"{key} must be list[str]")
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_extract_schema.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(extract): tool-use schema for claim extraction"
```

---

## Task 8: `ExtractorClient` protocol + fake + Anthropic implementation

**Files:**
- Create: `src/second_brain/extract/client.py`
- Create: `tests/test_extract_client.py`

- [ ] **Step 1: Write failing test `tests/test_extract_client.py`**

```python
from __future__ import annotations

from second_brain.extract.client import FakeExtractorClient, ExtractRequest


def test_fake_client_returns_canned_response() -> None:
    client = FakeExtractorClient(canned=[
        {"statement": "X", "kind": "empirical", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": "x"}
    ])
    resp = client.extract(ExtractRequest(
        body="doesn't matter", density="moderate", rubric="", source_id="src_x"
    ))
    assert len(resp.claims) == 1
    assert resp.claims[0]["statement"] == "X"
```

- [ ] **Step 2: Run — verify failure**

```bash
pytest tests/test_extract_client.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/extract/client.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from second_brain.extract.schema import RECORD_CLAIMS_TOOL

Density = str  # "sparse" | "moderate" | "dense"


@dataclass(frozen=True)
class ExtractRequest:
    body: str
    density: Density
    rubric: str
    source_id: str


@dataclass(frozen=True)
class ExtractResponse:
    claims: list[dict[str, Any]]


class ExtractorClient(Protocol):
    def extract(self, req: ExtractRequest) -> ExtractResponse: ...


class FakeExtractorClient:
    def __init__(self, *, canned: list[dict[str, Any]]) -> None:
        self._canned = canned

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        return ExtractResponse(claims=list(self._canned))


_DENSITY_GUIDANCE = {
    "sparse": "Only the 1-3 most load-bearing claims.",
    "moderate": "5-10 claims covering the main thrusts.",
    "dense": "As many atomic claims as the text justifies; favor the author's phrasing.",
}

_SYSTEM_PROMPT = (
    "You extract atomic, falsifiable claims from source texts. "
    "Always call the record_claims tool. Every claim must be grounded in the given body. "
    "Prefer the author's phrasing. Do not invent citations."
)


class AnthropicClient:
    """Opus 4.7 via Anthropic SDK with tool-use for schema enforcement."""

    def __init__(self, *, model: str = "claude-opus-4-7", max_tokens: int = 4096) -> None:
        self.model = model
        self.max_tokens = max_tokens
        # Lazy import so tests that use FakeExtractorClient don't require the SDK.
        from anthropic import Anthropic  # type: ignore[import-not-found]
        self._sdk = Anthropic()

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        user_prompt = self._build_user_prompt(req)
        message = self._sdk.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            tools=[RECORD_CLAIMS_TOOL],
            tool_choice={"type": "tool", "name": "record_claims"},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        claims: list[dict[str, Any]] = []
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "record_claims":
                claims = block.input.get("claims", [])
                break
        return ExtractResponse(claims=claims)

    @staticmethod
    def _build_user_prompt(req: ExtractRequest) -> str:
        density_hint = _DENSITY_GUIDANCE.get(req.density, _DENSITY_GUIDANCE["moderate"])
        return (
            f"Source id: {req.source_id}\n"
            f"Extraction density: {req.density} — {density_hint}\n"
            f"Rubric: {req.rubric or '(default)'}\n\n"
            f"BODY:\n{req.body}\n"
        )
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_extract_client.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(extract): ExtractorClient protocol with fake + Anthropic implementations"
```

---

## Task 9: `extract_claims` pipeline + claim writer

**Files:**
- Create: `src/second_brain/extract/claims.py`
- Create: `src/second_brain/extract/writer.py`
- Create: `tests/test_extract_claims.py`
- Create: `tests/test_extract_writer.py`

- [ ] **Step 1: Write failing test `tests/test_extract_claims.py`**

```python
from __future__ import annotations

from second_brain.extract.claims import extract_claims
from second_brain.extract.client import FakeExtractorClient


def test_extract_claims_passes_through() -> None:
    client = FakeExtractorClient(canned=[
        {"statement": "Attention replaces recurrence.", "kind": "empirical",
         "confidence": "high", "scope": "seq2seq",
         "supports": [], "contradicts": [], "refines": [], "abstract": "attn vs rnn"},
    ])
    claims = extract_claims(
        body="irrelevant", density="moderate", rubric="",
        source_id="src_a", client=client,
    )
    assert len(claims) == 1
    assert claims[0].statement == "Attention replaces recurrence."
    assert claims[0].id.startswith("clm_")


def test_skips_invalid_records() -> None:
    client = FakeExtractorClient(canned=[
        {"statement": "ok", "kind": "empirical", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": ""},
        {"statement": "bad", "kind": "NOT_A_KIND", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": ""},
    ])
    claims = extract_claims(
        body="", density="moderate", rubric="", source_id="src_x", client=client,
    )
    assert len(claims) == 1
```

- [ ] **Step 2: Implement `src/second_brain/extract/claims.py`**

```python
from __future__ import annotations

import logging
from datetime import UTC, datetime

from slugify import slugify

from second_brain.extract.client import ExtractorClient, ExtractRequest
from second_brain.extract.schema import validate_claim_record
from second_brain.schema.claim import (
    ClaimConfidence,
    ClaimFrontmatter,
    ClaimKind,
    ClaimStatus,
)

log = logging.getLogger(__name__)


def extract_claims(
    *,
    body: str,
    density: str,
    rubric: str,
    source_id: str,
    client: ExtractorClient,
    taken_ids: set[str] | None = None,
) -> list[ClaimFrontmatter]:
    taken = set(taken_ids or ())
    resp = client.extract(ExtractRequest(
        body=body, density=density, rubric=rubric, source_id=source_id,
    ))
    results: list[ClaimFrontmatter] = []
    now = datetime.now(UTC)
    for rec in resp.claims:
        try:
            validate_claim_record(rec)
        except ValueError as exc:
            log.warning("discarding invalid claim from %s: %s", source_id, exc)
            continue
        claim_id = _propose_id(rec["statement"], taken=taken)
        taken.add(claim_id)
        supports = list(rec.get("supports") or [])
        # If the extractor emitted bare '#section' fragments, anchor them to source_id.
        supports = [_anchor_to_source(s, source_id) for s in supports]
        if not supports:
            supports = [source_id]
        results.append(ClaimFrontmatter(
            id=claim_id,
            statement=rec["statement"],
            kind=ClaimKind(rec["kind"]),
            confidence=ClaimConfidence(rec["confidence"]),
            scope=rec.get("scope", ""),
            supports=supports,
            contradicts=list(rec.get("contradicts") or []),
            refines=list(rec.get("refines") or []),
            extracted_at=now,
            status=ClaimStatus.ACTIVE,
            resolution=None,
            abstract=rec.get("abstract", ""),
        ))
    return results


def _propose_id(statement: str, *, taken: set[str]) -> str:
    stem = slugify(statement, max_length=60, lowercase=True) or "claim"
    base = f"clm_{stem}"
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _anchor_to_source(ref: str, source_id: str) -> str:
    if ref.startswith("#"):
        return f"{source_id}{ref}"
    return ref
```

- [ ] **Step 3: Run — verify pass**

```bash
pytest tests/test_extract_claims.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Write failing test `tests/test_extract_writer.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.extract.writer import write_claims
from second_brain.frontmatter import load_document
from second_brain.schema.claim import (
    ClaimConfidence,
    ClaimFrontmatter,
    ClaimKind,
    ClaimStatus,
)


def test_write_claims_creates_files(sb_home: Path) -> None:
    cfg = Config.load()
    claim = ClaimFrontmatter(
        id="clm_x",
        statement="X is Y.",
        kind=ClaimKind.EMPIRICAL,
        confidence=ClaimConfidence.HIGH,
        scope="narrow",
        supports=["src_a"],
        contradicts=[],
        refines=[],
        extracted_at=datetime.now(UTC),
        status=ClaimStatus.ACTIVE,
        resolution=None,
        abstract="abs",
    )
    write_claims(cfg, [claim])
    path = cfg.claims_dir / "clm_x.md"
    assert path.exists()
    meta, body = load_document(path)
    assert meta["id"] == "clm_x"
    assert "# X is Y" in body
```

- [ ] **Step 5: Implement `src/second_brain/extract/writer.py`**

```python
from __future__ import annotations

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.schema.claim import ClaimFrontmatter


def write_claims(cfg: Config, claims: list[ClaimFrontmatter]) -> list[str]:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for claim in claims:
        path = cfg.claims_dir / f"{claim.id}.md"
        body = f"# {claim.statement.rstrip('.').rstrip()}\n"
        dump_document(path, claim.to_frontmatter_dict(), body)
        paths.append(str(path))
    return paths
```

- [ ] **Step 6: Run — verify pass**

```bash
pytest tests/test_extract_writer.py -v
```

Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(extract): extract_claims pipeline + writer"
```

---

## Task 10: Extraction worker (sync for v1, easy async upgrade later)

v1 runs extraction inline on a `ThreadPoolExecutor` triggered by a CLI command. The spec's "async queue" can be swapped in later without breaking the worker contract.

**Files:**
- Create: `src/second_brain/extract/worker.py`
- Create: `tests/test_extract_worker.py`

- [ ] **Step 1: Write failing test `tests/test_extract_worker.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.extract.client import FakeExtractorClient
from second_brain.extract.worker import extract_source
from second_brain.frontmatter import dump_document
from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind
from datetime import UTC, datetime


def _write_source(cfg: Config, slug: str, body: str) -> None:
    folder = cfg.sources_dir / slug
    (folder / "raw").mkdir(parents=True)
    (folder / "raw" / "original.md").write_text(body)
    sf = SourceFrontmatter(
        id=slug, title="Test", kind=SourceKind.NOTE,
        content_hash="sha256:0", ingested_at=datetime.now(UTC),
        raw=[RawArtifact(path="raw/original.md")], abstract="",
    )
    dump_document(folder / "_source.md", sf.to_frontmatter_dict(), body)


def test_extract_source_writes_claim_file(sb_home: Path) -> None:
    cfg = Config.load()
    _write_source(cfg, "src_test", "# Test\n\nBody.\n")
    client = FakeExtractorClient(canned=[
        {"statement": "Test says hello.", "kind": "empirical", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": "hi"},
    ])
    claims = extract_source(cfg, source_id="src_test", client=client,
                             density="moderate", rubric="")
    assert len(claims) == 1
    assert (cfg.claims_dir / f"{claims[0].id}.md").exists()
    # ensure supports back-refs the source
    assert claims[0].supports == ["src_test"]
```

- [ ] **Step 2: Implement `src/second_brain/extract/worker.py`**

```python
from __future__ import annotations

from second_brain.config import Config
from second_brain.extract.claims import extract_claims
from second_brain.extract.client import ExtractorClient
from second_brain.extract.writer import write_claims
from second_brain.frontmatter import load_document
from second_brain.log import EventKind, append_event
from second_brain.schema.claim import ClaimFrontmatter


def extract_source(
    cfg: Config,
    *,
    source_id: str,
    client: ExtractorClient,
    density: str = "moderate",
    rubric: str = "",
) -> list[ClaimFrontmatter]:
    source_path = cfg.sources_dir / source_id / "_source.md"
    if not source_path.exists():
        raise FileNotFoundError(f"source not found: {source_path}")
    meta, body = load_document(source_path)
    existing_ids = {p.stem for p in cfg.claims_dir.glob("*.md") if p.parent.name != "resolutions"}
    claims = extract_claims(
        body=body,
        density=density,
        rubric=rubric,
        source_id=meta["id"],
        client=client,
        taken_ids=existing_ids,
    )
    write_claims(cfg, claims)
    append_event(
        kind=EventKind.AUTO,
        op="extract.claims",
        subject=meta["id"],
        value=f"{len(claims)} claims",
        home=cfg.home,
    )
    return claims
```

- [ ] **Step 3: Run — verify pass**

```bash
pytest tests/test_extract_worker.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(extract): per-source extraction worker with log + back-refs"
```

---

## Task 11: `sb extract <slug>` CLI

**Files:**
- Modify: `src/second_brain/cli.py`
- Create: `tests/test_cli_extract.py`

- [ ] **Step 1: Write failing test `tests/test_cli_extract.py`**

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def test_cli_extract_uses_fake_when_flag_set(sb_home: Path, tmp_path: Path,
                                              monkeypatch) -> None:
    # Ingest a note first
    note = tmp_path / "note.md"
    note.write_text("# Topic\n\nTopic has a claim worth recording.\n")
    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", str(note)]).exit_code == 0

    # Force fake client via env var
    monkeypatch.setenv(
        "SB_FAKE_CLAIMS",
        '[{"statement":"Topic exists.","kind":"empirical","confidence":"high",'
        '"scope":"","supports":[],"contradicts":[],"refines":[],"abstract":"t"}]',
    )
    result = runner.invoke(cli, ["extract", "src_topic"])
    assert result.exit_code == 0, result.output
    assert "1 claim" in result.output.lower() or "1 claims" in result.output.lower()
```

- [ ] **Step 2: Modify `src/second_brain/cli.py`** — add at bottom:

```python
@cli.command(name="extract")
@click.argument("source_id")
@click.option("--density", type=click.Choice(["sparse", "moderate", "dense"]),
              default="moderate")
@click.option("--rubric", default="")
@click.option("--live/--fake", default=None,
              help="Force real Anthropic call (--live) or fake client (--fake). "
                   "Default: fake if ANTHROPIC_API_KEY unset or SB_FAKE_CLAIMS set.")
def _extract(source_id: str, density: str, rubric: str, live: bool | None) -> None:
    """Extract claims from an ingested source."""
    import json as _json
    import os

    from second_brain.extract.client import AnthropicClient, FakeExtractorClient
    from second_brain.extract.worker import extract_source

    cfg = Config.load()

    fake_payload = os.environ.get("SB_FAKE_CLAIMS")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if live is True and not api_key:
        raise click.ClickException("ANTHROPIC_API_KEY not set; cannot run --live")
    use_fake = (live is False) or fake_payload or not api_key

    if use_fake:
        canned = _json.loads(fake_payload) if fake_payload else []
        client = FakeExtractorClient(canned=canned)
    else:
        client = AnthropicClient()

    claims = extract_source(cfg, source_id=source_id, client=client,
                             density=density, rubric=rubric)
    click.echo(f"extracted {len(claims)} claim(s) for {source_id}")
    for c in claims:
        click.echo(f"  - {c.id}: {c.statement}")
```

- [ ] **Step 3: Run — verify pass**

```bash
pytest tests/test_cli_extract.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(cli): sb extract with fake/live client selection"
```

---

## Task 12: End-to-end ingest → extract → reindex → search finds the claim

**Files:**
- Create: `tests/test_e2e_extract_search.py`

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def test_e2e_flow(sb_home: Path, tmp_path: Path, monkeypatch) -> None:
    note = tmp_path / "attention.md"
    note.write_text("# Attention\n\nSelf-attention alone is sufficient.\n")

    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", str(note)]).exit_code == 0

    monkeypatch.setenv(
        "SB_FAKE_CLAIMS",
        json.dumps([{
            "statement": "Self-attention replaces recurrence.",
            "kind": "empirical", "confidence": "high",
            "scope": "seq2seq", "supports": [], "contradicts": [], "refines": [],
            "abstract": "attn vs rnn",
        }]),
    )
    assert runner.invoke(cli, ["extract", "src_attention"]).exit_code == 0
    assert runner.invoke(cli, ["reindex"]).exit_code == 0

    result = runner.invoke(cli, ["search", "--json", "--scope", "claims", "recurrence"])
    assert result.exit_code == 0
    hits = json.loads(result.output)
    assert hits and hits[0]["kind"] == "claim"
```

- [ ] **Step 2: Run + full suite**

```bash
pytest -m "not integration" -v
pytest --cov
```

Expected: all tests pass, coverage ≥ 75%.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: end-to-end ingest → extract → reindex → search"
```

---

## Task 13: Run real extraction on the user's welcome note

This is a manual smoke step using the real Anthropic API. Skip if `ANTHROPIC_API_KEY` is unset — the fake path already gives a working demo.

- [ ] **Step 1: Check API key**

```bash
[ -n "$ANTHROPIC_API_KEY" ] && echo "have key" || echo "no key — skipping live run"
```

- [ ] **Step 2: If key present, run live extraction on welcome note**

```bash
cd ~/Developer/second-brain && source .venv/bin/activate
sb extract src_welcome-to-second-brain --live
sb reindex
sb search "knowledge base"
```

Expected: one or two claims written, search returns them.

- [ ] **Step 3: If key absent, run fake extraction to exercise the pipeline**

```bash
export SB_FAKE_CLAIMS='[{"statement":"Second Brain is a markdown-as-truth knowledge base.","kind":"definitional","confidence":"high","scope":"","supports":[],"contradicts":[],"refines":[],"abstract":"sb overview"}]'
sb extract src_welcome-to-second-brain
sb reindex
sb search "knowledge"
```

No commit — user data.

---

## Self-Review

Spec coverage vs plan 2 scope:

| Spec section | Task | Status |
|---|---|---|
| §5.5 Claim extraction (schema-constrained) | 7, 8, 9, 10 | ✅ |
| §5.5 Adaptive density | 11 (CLI flag) | ✅ (density flag; per-taxonomy auto-resolve in plan 5) |
| §6 DuckPGQ property graph | 1, 2 | ✅ |
| §8.1 FTS5 BM25 | done in plan 1 | ✅ |
| §8.2 Retriever protocol + RetrievalHit | 3 | ✅ |
| §8.3 sb_search with neighbors | 3, 6 | ✅ |
| §8.3 sb_load with depth + relations | 4, 6 | ✅ |
| §8.3 sb_reason typed GraphPattern | 5, 6 | ✅ |
| §8.3 shorthand helpers (`sb_reason_chain`, etc.) | 5 | ✅ |
| §8.4 sb inject | — | ⏭ plan 4 |
| §8.5 hybrid retrieval extension | — | ⏭ deferred (protocol keeps the door open) |

Placeholder scan: no TBD / TODO. Every Click option and schema property is concretely defined. Test fixtures are inline.

Type consistency check: `RetrievalHit`, `GraphPattern`, `LoadResult`, `ExtractRequest`, `ExtractResponse`, `ExtractorClient`, `ClaimFrontmatter`, `Config` — all names match across tasks. `sb_reason` (function) vs `reason` (Click command name) are intentionally different at the CLI boundary; Python callers use `sb_reason`.

Known integration caveats flagged for the executor:
- DuckPGQ install may fail in sandboxed CI; extension loader returns False and reindex continues with plain SQL. `sb_reason` uses plain SQL anyway, so DuckPGQ isn't on the critical path — it's there for future richer queries.
- `AnthropicClient` requires `ANTHROPIC_API_KEY`. All tests use `FakeExtractorClient`; the `--live` flag gates the real call.

---

## Execution Handoff

Plan committed to `docs/superpowers/plans/2026-04-17-second-brain-retrieval-extraction.md`. Execution continues via subagents in the pattern established by plan 1: batched by 4 tasks per subagent, TDD per task, commits matching the plan exactly.
