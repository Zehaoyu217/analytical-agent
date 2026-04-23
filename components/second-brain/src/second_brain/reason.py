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
    MATCH is available in DuckDB >=1.1 but is slower for small graphs and adds
    a hard dependency - plain SQL is adequate here.
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
