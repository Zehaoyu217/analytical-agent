"""Thin sqlite-vec wrapper for claim + source embeddings.

Schema (per virtual vec0 table):
    CREATE VIRTUAL TABLE claim_vecs USING vec0(
        id TEXT PRIMARY KEY,
        embedding float[<dim>]
    );

A tiny sidecar ``vec_meta`` table records the dim so reopening the store
can detect schema drift instead of silently corrupting queries.

``topk`` uses cosine/L2 distance (sqlite-vec default is L2 on unit-length
vectors, which is monotonic in cosine). Lower distance = better match.
"""
from __future__ import annotations

import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from second_brain.embed.base import EmbeddingVector

Kind = Literal["claim", "source", "chunk"]

_TABLE = {"claim": "claim_vecs", "source": "source_vecs", "chunk": "chunk_vecs"}


def _serialize(vec: EmbeddingVector) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


class VectorStore:
    """Context-managed sqlite-vec store."""

    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self.conn = conn
        self.path = path

    @classmethod
    @contextmanager
    def open(cls, path: Path) -> Iterator[VectorStore]:
        import sqlite_vec  # type: ignore[import-not-found]

        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            yield cls(conn, path)
            conn.commit()
        finally:
            conn.close()

    def ensure_schema(self, dim: int) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS vec_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        existing = self.conn.execute(
            "SELECT value FROM vec_meta WHERE key = 'dim'"
        ).fetchone()
        if existing:
            recorded = int(existing[0])
            if recorded != dim:
                raise ValueError(
                    f"vector store already initialized with dim={recorded}, refusing dim={dim}"
                )
            return
        self.conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS claim_vecs USING vec0("
            f"id TEXT PRIMARY KEY, embedding float[{dim}])"
        )
        self.conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS source_vecs USING vec0("
            f"id TEXT PRIMARY KEY, embedding float[{dim}])"
        )
        self.conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vecs USING vec0("
            f"id TEXT PRIMARY KEY, embedding float[{dim}])"
        )
        self.conn.execute(
            "INSERT INTO vec_meta(key, value) VALUES ('dim', ?)", (str(dim),)
        )

    def upsert(self, kind: Kind, id: str, embedding: EmbeddingVector) -> None:
        table = _TABLE[kind]
        # Virtual vec0 tables don't support ON CONFLICT; delete-then-insert.
        self.conn.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
        self.conn.execute(
            f"INSERT INTO {table}(id, embedding) VALUES (?, ?)",
            (id, _serialize(embedding)),
        )

    def topk(
        self,
        kind: Kind,
        query_embedding: EmbeddingVector,
        k: int,
    ) -> list[tuple[str, float]]:
        if k <= 0:
            return []
        table = _TABLE[kind]
        rows = self.conn.execute(
            f"SELECT id, distance FROM {table} "
            "WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance",
            (_serialize(query_embedding), k),
        ).fetchall()
        return [(r[0], float(r[1])) for r in rows]
