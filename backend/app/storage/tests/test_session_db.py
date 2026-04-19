"""Tests for app.storage.session_db — SessionDB CRUD + FTS5 + jitter retry."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from app.storage.session_db import SessionDB


@pytest.fixture
def db(tmp_path: Path) -> SessionDB:
    return SessionDB(db_path=tmp_path / "test_sessions.db")


# ── Basic CRUD ─────────────────────────────────────────────────────────────────

def test_create_and_get_session(db: SessionDB) -> None:
    db.create_session(id="s1", model="gpt-4", goal="test goal", source="chat")
    s = db.get_session("s1")
    assert s is not None
    assert s.id == "s1"
    assert s.model == "gpt-4"
    assert s.goal == "test goal"
    assert s.source == "chat"


def test_get_session_returns_none_for_unknown(db: SessionDB) -> None:
    assert db.get_session("does-not-exist") is None


def test_append_message_and_list(db: SessionDB) -> None:
    db.create_session(id="s2", source="chat")
    db.append_message(session_id="s2", role="user", content="hello")
    db.append_message(session_id="s2", role="assistant", content="hi there")
    db.append_message(session_id="s2", role="user", content="bye")
    s = db.get_session("s2", include_messages=True)
    assert s is not None
    assert len(s.messages) == 3
    roles = [m.role for m in s.messages]
    assert "user" in roles
    assert "assistant" in roles


def test_finalize_updates_step_count_and_outcome(db: SessionDB) -> None:
    db.create_session(id="s3", source="chat")
    db.finalize_session(id="s3", outcome="ok", step_count=5,
                        input_tokens=100, output_tokens=200)
    s = db.get_session("s3")
    assert s is not None
    assert s.outcome == "ok"
    assert s.step_count == 5
    assert s.input_tokens == 100
    assert s.output_tokens == 200


# ── FTS5 Search ────────────────────────────────────────────────────────────────

def test_fts5_search_finds_match(db: SessionDB) -> None:
    db.create_session(id="s4", source="chat")
    db.append_message(session_id="s4", role="user",
                      content="tell me about interest rates in Q3")
    results = db.search("interest rates")
    assert len(results) >= 1
    assert results[0].session_id == "s4"


def test_fts5_search_no_match_returns_empty(db: SessionDB) -> None:
    db.create_session(id="s5", source="chat")
    db.append_message(session_id="s5", role="user", content="only fruit topics")
    results = db.search("xyzzy_nonexistent_42")
    assert results == []


# ── Jitter retry ───────────────────────────────────────────────────────────────

def test_jitter_retry_on_lock(db: SessionDB) -> None:
    """Verify jitter retry eventually succeeds after repeated OperationalError('locked')."""
    original_connect = db._connect

    call_count = 0

    def flaky_connect() -> sqlite3.Connection:
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise sqlite3.OperationalError("database is locked")
        return original_connect()

    with patch.object(db, "_connect", side_effect=flaky_connect):
        # Should succeed after 3 failed attempts
        db.create_session(id="s_retry", source="chat")

    assert call_count >= 4


# ── list_sessions with source filter ──────────────────────────────────────────

def test_list_sessions_filtered_by_source(db: SessionDB) -> None:
    db.create_session(id="chat-1", source="chat")
    db.create_session(id="cron-1", source="cron")
    db.create_session(id="chat-2", source="chat")

    chat_sessions = db.list_sessions(source="chat")
    assert all(s.source == "chat" for s in chat_sessions)
    assert len(chat_sessions) == 2

    cron_sessions = db.list_sessions(source="cron")
    assert len(cron_sessions) == 1
    assert cron_sessions[0].id == "cron-1"

    all_sessions = db.list_sessions()
    assert len(all_sessions) == 3
