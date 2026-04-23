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
        store.insert_chunk(
            id="chk_a_001",
            source_id="src_a",
            ordinal=1,
            section_title="Intro",
            body="attention chunk body",
            start_char=0,
            end_char=20,
            page_start=1,
            page_end=1,
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


def test_chunk_load_returns_provenance(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    result = load_node(cfg, "chk_a_001", depth=0)
    assert result.root["kind"] == "chunk"
    assert result.root["source_id"] == "src_a"
    assert result.root["page_start"] == 1
