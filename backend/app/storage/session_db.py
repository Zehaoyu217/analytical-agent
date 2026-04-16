"""SessionDB — SQLite + FTS5 session store.

Replaces non-queryable YAML trace files with a single queryable database.
All runtime data (messages, sessions, cron job definitions) lives here.

Key design points:
- WAL mode: concurrent readers do not block writer
- FTS5 content-table: full-text search over message content
- Jitter retry: breaks convoy effect under concurrent reads (20–150ms, 15 tries)
- WAL checkpoint every 50 writes: prevents unbounded WAL file growth
"""
from __future__ import annotations

import json
import logging
import random
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    model         TEXT,
    title         TEXT,
    goal          TEXT,
    outcome       TEXT,
    source        TEXT DEFAULT 'chat',
    step_count    INTEGER DEFAULT 0,
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT,
    tool_calls  TEXT,
    tool_result TEXT,
    timestamp   REAL NOT NULL,
    step_index  INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
END;

CREATE TABLE IF NOT EXISTS cron_jobs (
    id              TEXT PRIMARY KEY,
    schedule        TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    enabled         INTEGER DEFAULT 1,
    created_at      REAL NOT NULL,
    last_run_at     REAL,
    next_run_at     REAL,
    last_session_id TEXT REFERENCES sessions(id)
);
"""


@dataclass
class Session:
    id: str
    created_at: float
    model: str | None
    title: str | None
    goal: str | None
    outcome: str | None
    source: str
    step_count: int
    input_tokens: int
    output_tokens: int
    messages: list[Message] = field(default_factory=list)


@dataclass
class Message:
    id: str
    session_id: str
    role: str
    content: str | None
    tool_calls: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    timestamp: float
    step_index: int | None


@dataclass
class SearchResult:
    session_id: str
    message_id: str
    snippet: str
    role: str
    timestamp: float


@dataclass
class CronJobRecord:
    """Thin storage-layer mirror of a cron_jobs row.

    Fields map 1:1 to the DB columns.  The scheduler layer converts these
    to/from its own ``CronJob`` Pydantic model — no cross-layer import needed.
    """

    id: str
    schedule: str
    prompt: str
    enabled: bool
    created_at: float
    last_run_at: float | None
    next_run_at: float | None
    last_session_id: str | None


def _jitter_retry(fn: Any, max_attempts: int = 15) -> Any:
    """Retry on SQLite lock errors with random backoff (20–150ms)."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == max_attempts - 1:
                raise
            time.sleep(random.uniform(0.02, 0.15))
    # unreachable — last attempt re-raises
    raise RuntimeError("unreachable")  # pragma: no cover


class SessionDB:
    """Thread-safe SQLite session store with FTS5 full-text search."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_count = 0
        self._init_db()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

    def _checkpoint(self, conn: sqlite3.Connection) -> None:
        self._write_count += 1
        if self._write_count % 50 == 0:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

    # ── Write helpers ──────────────────────────────────────────────────────

    def create_session(
        self,
        id: str,
        model: str | None = None,
        goal: str | None = None,
        source: str = "chat",
    ) -> None:
        """Insert a new session row. Idempotent — ignores duplicate id."""
        trimmed_goal = (goal or "")[:300] or None

        def _insert() -> None:
            with self._connect() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO sessions
                       (id, created_at, model, goal, source)
                       VALUES (?, ?, ?, ?, ?)""",
                    (id, time.time(), model, trimmed_goal, source),
                )
                self._checkpoint(conn)

        _jitter_retry(_insert)

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: dict[str, Any] | None = None,
        tool_result: dict[str, Any] | None = None,
        step_index: int | None = None,
    ) -> str:
        """Append a message row and return its generated id."""
        msg_id = str(uuid.uuid4())
        tc_json = json.dumps(tool_calls) if tool_calls is not None else None
        tr_json = json.dumps(tool_result) if tool_result is not None else None

        def _insert() -> None:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO messages
                       (id, session_id, role, content, tool_calls, tool_result,
                        timestamp, step_index)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (msg_id, session_id, role, content, tc_json, tr_json,
                     time.time(), step_index),
                )
                self._checkpoint(conn)

        _jitter_retry(_insert)
        return msg_id

    def finalize_session(
        self,
        id: str,
        outcome: str | None = None,
        step_count: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Update session summary fields after the run completes."""
        trimmed_outcome = (outcome or "")[:500] or None

        def _update() -> None:
            with self._connect() as conn:
                conn.execute(
                    """UPDATE sessions
                       SET outcome=?, step_count=?, input_tokens=?, output_tokens=?
                       WHERE id=?""",
                    (trimmed_outcome, step_count, input_tokens, output_tokens, id),
                )
                self._checkpoint(conn)

        _jitter_retry(_update)

    def list_cron_jobs(self, enabled_only: bool = False) -> list[CronJobRecord]:
        """Return all cron job rows, optionally filtering to enabled ones only."""
        with self._connect() as conn:
            if enabled_only:
                rows = conn.execute(
                    "SELECT * FROM cron_jobs WHERE enabled=1 ORDER BY created_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cron_jobs ORDER BY created_at"
                ).fetchall()
            return [_row_to_cron_job(row) for row in rows]

    def upsert_cron_job(self, job: Any) -> None:
        """Insert or replace a cron_jobs row from a CronJob-like object."""

        def _upsert() -> None:
            with self._connect() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO cron_jobs
                       (id, schedule, prompt, enabled, created_at,
                        last_run_at, next_run_at, last_session_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job.id,
                        job.schedule,
                        job.prompt,
                        int(job.enabled),
                        job.created_at,
                        getattr(job, "last_run_at", None),
                        getattr(job, "next_run_at", None),
                        getattr(job, "last_session_id", None),
                    ),
                )
                self._checkpoint(conn)

        _jitter_retry(_upsert)

    def delete_cron_job(self, job_id: str) -> None:
        """Delete a cron_jobs row by id."""

        def _delete() -> None:
            with self._connect() as conn:
                conn.execute("DELETE FROM cron_jobs WHERE id=?", (job_id,))
                self._checkpoint(conn)

        _jitter_retry(_delete)

    def update_cron_job(self, job_id: str, **kwargs: Any) -> None:
        """Upsert arbitrary fields on a cron_jobs row."""
        if not kwargs:
            return
        cols = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [job_id]

        def _update() -> None:
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE cron_jobs SET {cols} WHERE id=?",  # noqa: S608
                    vals,
                )
                self._checkpoint(conn)

        _jitter_retry(_update)

    # ── Read helpers ───────────────────────────────────────────────────────

    def get_session(self, id: str, include_messages: bool = False) -> Session | None:
        """Return a Session or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id=?", (id,)
            ).fetchone()
            if row is None:
                return None
            session = _row_to_session(row)
            if include_messages:
                msgs = conn.execute(
                    "SELECT * FROM messages WHERE session_id=? ORDER BY timestamp",
                    (id,),
                ).fetchall()
                session.messages = [_row_to_message(m) for m in msgs]
            return session

    def list_sessions(
        self,
        limit: int = 50,
        source: str | None = None,
    ) -> list[Session]:
        """Return recent sessions, newest first."""
        with self._connect() as conn:
            if source is not None:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE source=? ORDER BY created_at DESC LIMIT ?",
                    (source, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [_row_to_session(r) for r in rows]

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Full-text search across message content. Returns up to `limit` results."""
        limit = min(limit, 20)
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT m.id, m.session_id, m.role, m.timestamp,
                          snippet(messages_fts, 0, '<b>', '</b>', '…', 32) AS snip
                   FROM messages_fts
                   JOIN messages m ON messages_fts.rowid = m.rowid
                   WHERE messages_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [
                SearchResult(
                    session_id=r["session_id"],
                    message_id=r["id"],
                    snippet=r["snip"] or "",
                    role=r["role"],
                    timestamp=r["timestamp"],
                )
                for r in rows
            ]


# ── Row converters ──────────────────────────────────────────────────────────

def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        created_at=row["created_at"],
        model=row["model"],
        title=row["title"],
        goal=row["goal"],
        outcome=row["outcome"],
        source=row["source"] or "chat",
        step_count=row["step_count"] or 0,
        input_tokens=row["input_tokens"] or 0,
        output_tokens=row["output_tokens"] or 0,
    )


def _row_to_cron_job(row: sqlite3.Row) -> CronJobRecord:
    return CronJobRecord(
        id=row["id"],
        schedule=row["schedule"],
        prompt=row["prompt"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        last_run_at=row["last_run_at"],
        next_run_at=row["next_run_at"],
        last_session_id=row["last_session_id"],
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    tc = row["tool_calls"]
    tr = row["tool_result"]
    return Message(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        tool_calls=json.loads(tc) if tc else None,
        tool_result=json.loads(tr) if tr else None,
        timestamp=row["timestamp"],
        step_index=row["step_index"],
    )
