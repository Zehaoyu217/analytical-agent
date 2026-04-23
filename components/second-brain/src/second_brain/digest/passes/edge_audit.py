"""Edge-audit digest pass.

Inputs:
    - All edges whose destination claim has ``status: retracted``.
      Preferred source is the graph DuckDB (``cfg.duckdb_path``); when the DB
      is missing (fresh KB) we fall back to walking claim markdown frontmatter
      and treating ``supports`` / ``contradicts`` / ``refines`` as edges.

Output:
    - One ``drop_edge`` entry per edge pointing at a retracted claim.

Pure graph walk — no Claude call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry
from second_brain.lint.snapshot import load_snapshot
from second_brain.schema.claim import ClaimStatus

_CLAIM_RELATIONS = ("supports", "contradicts", "refines")


@dataclass(frozen=True)
class _Edge:
    src_id: str
    dst_id: str
    relation: str


def _retracted_ids_from_snapshot(cfg: Config) -> set[str]:
    snap = load_snapshot(cfg)
    return {cid for cid, claim in snap.claims.items() if claim.status == ClaimStatus.RETRACTED}


def _edges_from_duckdb(path) -> list[_Edge]:
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return []
    try:
        try:
            rows = conn.execute(
                "SELECT src_id, dst_id, relation FROM edges"
            ).fetchall()
        except duckdb.Error:
            # Table missing — DB exists but not populated yet.
            return []
        return [_Edge(src_id=r[0], dst_id=r[1], relation=r[2]) for r in rows]
    finally:
        conn.close()


def _edges_from_markdown(cfg: Config) -> list[_Edge]:
    snap = load_snapshot(cfg)
    out: list[_Edge] = []
    for cid, claim in snap.claims.items():
        for relation in _CLAIM_RELATIONS:
            for target in getattr(claim, relation):
                tid = target.split("#", 1)[0]
                out.append(_Edge(src_id=cid, dst_id=tid, relation=relation))
    return out


def _collect_edges(cfg: Config) -> list[_Edge]:
    path = cfg.duckdb_path
    if path.exists():
        edges = _edges_from_duckdb(path)
        if edges:
            return edges
    return _edges_from_markdown(cfg)


class EdgeAuditPass:
    """Flags edges whose destination claim has been retracted."""

    prefix = "e"
    section = "Edge audit"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        retracted = _retracted_ids_from_snapshot(cfg)
        if not retracted:
            return []
        edges = _collect_edges(cfg)

        entries: list[DigestEntry] = []
        seen: set[tuple[str, str, str]] = set()
        for edge in edges:
            if edge.dst_id not in retracted:
                continue
            key = (edge.src_id, edge.dst_id, edge.relation)
            if key in seen:
                continue
            seen.add(key)
            payload: dict[str, Any] = {
                "action": "drop_edge",
                "src_id": edge.src_id,
                "dst_id": edge.dst_id,
                "relation": edge.relation,
            }
            entries.append(
                DigestEntry(
                    id="",
                    section=self.section,
                    line=(
                        f"Drop {edge.relation} edge {edge.src_id} → {edge.dst_id} "
                        "(target retracted)?"
                    ),
                    action=payload,
                )
            )
        # Stable order for deterministic ids in Batch 2.
        entries.sort(key=lambda e: (e.action["src_id"], e.action["dst_id"], e.action["relation"]))
        return entries
