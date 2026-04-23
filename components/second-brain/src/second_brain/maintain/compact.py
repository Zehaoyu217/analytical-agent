"""Index maintenance ops — FTS5 optimize + VACUUM + DuckDB CHECKPOINT."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from second_brain.config import Config
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore


@dataclass(frozen=True)
class CompactResult:
    before: int
    after: int


def _size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def compact_fts(cfg: Config) -> CompactResult:
    before = _size(cfg.fts_path)
    if before == 0:
        return CompactResult(0, 0)
    with FtsStore.open(cfg.fts_path) as store:
        tables = store.list_tables()
        if "claim_fts" in tables:
            store.conn.execute("INSERT INTO claim_fts(claim_fts) VALUES('optimize')")
        if "source_fts" in tables:
            store.conn.execute("INSERT INTO source_fts(source_fts) VALUES('optimize')")
        store.conn.commit()
        # VACUUM cannot run inside a transaction — sqlite3's default isolation
        # opens one implicitly. Commit first, then switch to autocommit for VACUUM.
        store.conn.isolation_level = None
        store.conn.execute("VACUUM")
    return CompactResult(before=before, after=_size(cfg.fts_path))


def compact_duckdb(cfg: Config) -> CompactResult:
    before = _size(cfg.duckdb_path)
    if before == 0:
        return CompactResult(0, 0)
    with DuckStore.open(cfg.duckdb_path) as store:
        store.conn.execute("CHECKPOINT")
    return CompactResult(before=before, after=_size(cfg.duckdb_path))
