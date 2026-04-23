from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import duckdb

DDL = """
CREATE TABLE IF NOT EXISTS sources (
  id              TEXT PRIMARY KEY,
  slug            TEXT,
  title           TEXT,
  kind            TEXT,
  year            INTEGER,
  habit_taxonomy  TEXT,
  content_hash    TEXT,
  abstract        TEXT,
  ingested_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claims (
  id               TEXT PRIMARY KEY,
  statement        TEXT,
  body             TEXT,
  abstract         TEXT,
  kind             TEXT,
  confidence_claim TEXT,
  status           TEXT,
  resolution       TEXT
);

CREATE TABLE IF NOT EXISTS center_nodes (
  id               TEXT PRIMARY KEY,
  kind             TEXT NOT NULL,
  title            TEXT NOT NULL,
  status           TEXT,
  summary          TEXT,
  confidence       DOUBLE,
  updated_at       TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
  id               TEXT PRIMARY KEY,
  source_id        TEXT NOT NULL,
  ordinal          INTEGER NOT NULL,
  section_title    TEXT,
  body             TEXT,
  start_char       INTEGER,
  end_char         INTEGER,
  page_start       INTEGER,
  page_end         INTEGER
);

CREATE TABLE IF NOT EXISTS edges (
  src_id           TEXT NOT NULL,
  dst_id           TEXT NOT NULL,
  relation         TEXT NOT NULL,
  confidence_edge  TEXT NOT NULL,
  rationale        TEXT,
  source_markdown  TEXT,
  PRIMARY KEY (src_id, dst_id, relation)
);

CREATE INDEX IF NOT EXISTS edges_src_rel ON edges(src_id, relation);
CREATE INDEX IF NOT EXISTS edges_dst_rel ON edges(dst_id, relation);
CREATE INDEX IF NOT EXISTS chunks_source_idx ON chunks(source_id, ordinal);
"""


class DuckStore:
    """Thin DuckDB wrapper. Property-graph view is added in plan 2."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, path: Path) -> None:
        self.conn = conn
        self.path = path

    @classmethod
    @contextmanager
    def open(cls, path: Path) -> Iterator[DuckStore]:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(path))
        try:
            yield cls(conn, path)
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        self.conn.execute(DDL)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
        return sorted(r[0] for r in rows)

    def insert_source(
        self,
        *,
        id: str,
        slug: str,
        title: str,
        kind: str,
        year: int | None,
        habit_taxonomy: str | None,
        content_hash: str,
        abstract: str,
        ingested_at: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO sources (id, slug, title, kind, year, habit_taxonomy, "
            "content_hash, abstract, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [id, slug, title, kind, year, habit_taxonomy, content_hash, abstract, ingested_at],
        )

    def insert_claim(
        self,
        *,
        id: str,
        statement: str,
        body: str,
        abstract: str,
        kind: str,
        confidence: str,
        status: str,
        resolution: str | None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO claims (id, statement, body, abstract, kind, "
            "confidence_claim, status, resolution) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [id, statement, body, abstract, kind, confidence, status, resolution],
        )

    def insert_center_node(
        self,
        *,
        id: str,
        kind: str,
        title: str,
        status: str,
        summary: str,
        confidence: float,
        updated_at: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO center_nodes (id, kind, title, status, summary, confidence, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [id, kind, title, status, summary, confidence, updated_at],
        )

    def insert_chunk(
        self,
        *,
        id: str,
        source_id: str,
        ordinal: int,
        section_title: str,
        body: str,
        start_char: int,
        end_char: int,
        page_start: int | None,
        page_end: int | None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO chunks (id, source_id, ordinal, section_title, body, start_char, end_char, page_start, page_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [id, source_id, ordinal, section_title, body, start_char, end_char, page_start, page_end],
        )

    def insert_edge(
        self,
        *,
        src_id: str,
        dst_id: str,
        relation: str,
        confidence: str,
        rationale: str | None,
        source_markdown: str,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO edges (src_id, dst_id, relation, "
            "confidence_edge, rationale, source_markdown) VALUES (?, ?, ?, ?, ?, ?)",
            [src_id, dst_id, relation, confidence, rationale, source_markdown],
        )

    @staticmethod
    def atomic_swap(*, staging: Path, target: Path) -> None:
        """Rename staging DB file to target. POSIX atomic on same filesystem."""
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_suffix(target.suffix + ".prev")
            if backup.exists():
                backup.unlink()
            os.replace(target, backup)
        os.replace(staging, target)
        # Clean up empty staging parent if we made it.
        with suppress(OSError):
            shutil.rmtree(staging.parent, ignore_errors=False)
