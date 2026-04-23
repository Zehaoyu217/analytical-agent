from __future__ import annotations

import shutil
from pathlib import Path

from second_brain.config import Config
from second_brain.reindex import reindex
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def _populate(sb_home: Path) -> None:
    shutil.copytree(FIXTURES / "src_hello", sb_home / "sources" / "src_hello")


def test_reindex_empty_home_produces_empty_dbs(sb_home: Path) -> None:
    cfg = Config.load()
    reindex(cfg)
    assert cfg.duckdb_path.exists()
    assert cfg.fts_path.exists()
    with DuckStore.open(cfg.duckdb_path) as store:
        assert store.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0


def test_reindex_populates_source_row(sb_home: Path) -> None:
    _populate(sb_home)
    cfg = Config.load()
    reindex(cfg)
    with DuckStore.open(cfg.duckdb_path) as store:
        rows = store.conn.execute("SELECT id, title, habit_taxonomy FROM sources").fetchall()
    assert rows == [("src_hello", "Hello", "notes/personal")]


def test_reindex_populates_fts(sb_home: Path) -> None:
    _populate(sb_home)
    cfg = Config.load()
    reindex(cfg)
    with FtsStore.open(cfg.fts_path) as store:
        hits = store.search_sources("hello", k=5)
    assert hits and hits[0][0] == "src_hello"


def test_reindex_is_deterministic(sb_home: Path) -> None:
    _populate(sb_home)
    cfg = Config.load()
    reindex(cfg)
    first = cfg.duckdb_path.read_bytes()
    cfg.duckdb_path.unlink()
    cfg.fts_path.unlink()
    reindex(cfg)
    second = cfg.duckdb_path.read_bytes()
    # DuckDB file content isn't byte-identical across runs, so query instead.
    with DuckStore.open(cfg.duckdb_path) as store:
        ids = [r[0] for r in store.conn.execute("SELECT id FROM sources ORDER BY id").fetchall()]
    assert ids == ["src_hello"]
