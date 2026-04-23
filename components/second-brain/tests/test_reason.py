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
