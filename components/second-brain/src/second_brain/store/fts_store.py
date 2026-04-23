from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
  source_id UNINDEXED,
  title,
  abstract,
  processed_body,
  taxonomy,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS claim_fts USING fts5(
  claim_id UNINDEXED,
  statement,
  abstract,
  body,
  taxonomy,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS center_fts USING fts5(
  center_id UNINDEXED,
  kind UNINDEXED,
  title,
  summary,
  body,
  tags,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
  chunk_id UNINDEXED,
  source_id UNINDEXED,
  source_title,
  section_title,
  body,
  taxonomy,
  page_span,
  tokenize = 'unicode61 remove_diacritics 2'
);
"""

# Column weight orderings match the virtual table definitions above.
SOURCE_BM25_WEIGHTS = "3.0, 2.0, 1.0, 0.5"
CLAIM_BM25_WEIGHTS = "3.0, 2.0, 1.0, 0.5"
CENTER_BM25_WEIGHTS = "3.0, 2.0, 1.0, 0.3"
CHUNK_BM25_WEIGHTS = "2.0, 2.5, 1.0, 0.3, 0.2"


class FtsStore:
    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self.conn = conn
        self.path = path

    @classmethod
    @contextmanager
    def open(cls, path: Path) -> Iterator[FtsStore]:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        try:
            yield cls(conn, path)
            conn.commit()
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        self.conn.executescript(DDL)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','virtual') OR name LIKE '%_fts'"
        ).fetchall()
        return sorted(r[0] for r in rows)

    def insert_source(
        self,
        *,
        source_id: str,
        title: str,
        abstract: str,
        processed_body: str,
        taxonomy: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO source_fts (source_id, title, abstract, processed_body, taxonomy) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_id, title, abstract, processed_body, taxonomy),
        )

    def insert_claim(
        self,
        *,
        claim_id: str,
        statement: str,
        abstract: str,
        body: str,
        taxonomy: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO claim_fts (claim_id, statement, abstract, body, taxonomy) "
            "VALUES (?, ?, ?, ?, ?)",
            (claim_id, statement, abstract, body, taxonomy),
        )

    def insert_center(
        self,
        *,
        center_id: str,
        kind: str,
        title: str,
        summary: str,
        body: str,
        tags: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO center_fts (center_id, kind, title, summary, body, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (center_id, kind, title, summary, body, tags),
        )

    def insert_chunk(
        self,
        *,
        chunk_id: str,
        source_id: str,
        source_title: str,
        section_title: str,
        body: str,
        taxonomy: str,
        page_span: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO chunk_fts (chunk_id, source_id, source_title, section_title, body, taxonomy, page_span) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, source_id, source_title, section_title, body, taxonomy, page_span),
        )

    def search_sources(self, query: str, k: int) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            f"SELECT source_id, -bm25(source_fts, {SOURCE_BM25_WEIGHTS}) AS score "
            "FROM source_fts WHERE source_fts MATCH ? ORDER BY score DESC LIMIT ?",
            (query, k),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def search_centers(self, query: str, k: int) -> list[tuple[str, str, float, str]]:
        try:
            rows = self.conn.execute(
                f"SELECT center_id, kind, -bm25(center_fts, {CENTER_BM25_WEIGHTS}) AS score "
                "FROM center_fts WHERE center_fts MATCH ? ORDER BY score DESC LIMIT ?",
                (query, k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(r[0], r[1], r[2], "center") for r in rows]

    def search_chunks(
        self, query: str, k: int
    ) -> list[tuple[str, str, str, str, str, float, str]]:
        try:
            rows = self.conn.execute(
                f"SELECT chunk_id, source_id, source_title, section_title, page_span, "
                f"-bm25(chunk_fts, {CHUNK_BM25_WEIGHTS}) AS score, "
                "snippet(chunk_fts, 4, '', '', ' … ', 18) AS snippet "
                "FROM chunk_fts WHERE chunk_fts MATCH ? ORDER BY score DESC LIMIT ?",
                (query, k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]

    def search_claims(self, query: str, k: int) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            f"SELECT claim_id, -bm25(claim_fts, {CLAIM_BM25_WEIGHTS}) AS score "
            "FROM claim_fts WHERE claim_fts MATCH ? ORDER BY score DESC LIMIT ?",
            (query, k),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    @staticmethod
    def atomic_swap(*, staging: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_suffix(target.suffix + ".prev")
            if backup.exists():
                backup.unlink()
            os.replace(target, backup)
        os.replace(staging, target)
        with suppress(OSError):
            staging.parent.rmdir()
