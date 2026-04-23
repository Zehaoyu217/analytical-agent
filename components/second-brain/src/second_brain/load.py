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
    row = store.conn.execute(
        "SELECT id, kind, title, status, summary, confidence FROM center_nodes WHERE id = ?",
        [node_id],
    ).fetchone()
    if row:
        return {
            "id": row[0],
            "kind": row[1],
            "title": row[2],
            "status": row[3],
            "summary": row[4],
            "confidence": row[5],
        }
    row = store.conn.execute(
        "SELECT id, source_id, ordinal, section_title, body, page_start, page_end "
        "FROM chunks WHERE id = ?",
        [node_id],
    ).fetchone()
    if row:
        return {
            "id": row[0],
            "kind": "chunk",
            "source_id": row[1],
            "ordinal": row[2],
            "section_title": row[3],
            "text": row[4],
            "page_start": row[5],
            "page_end": row[6],
        }
    return None
