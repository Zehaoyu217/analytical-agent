"""Tests for TraceRecorder → SessionDB integration (H2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.session_db import SessionDB
from app.trace.events import Grade
from app.trace.publishers import TraceSession


@pytest.fixture
def tmp_db(tmp_path: Path) -> SessionDB:
    return SessionDB(db_path=tmp_path / "test.db")


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "traces"
    d.mkdir()
    return d


def test_recorder_writes_to_session_db(
    tmp_db: SessionDB,
    output_dir: Path,
) -> None:
    """A complete TraceSession run should create a session row + messages in the DB."""
    session_id = "test-session-001"

    with TraceSession(
        session_id=session_id,
        level=1,
        level_label="test",
        input_query="what is 2+2?",
        trace_mode="always",
        output_dir=output_dir,
        session_db=tmp_db,
    ):
        # Publish a minimal LLM call via the recorder's on_event path
        from app.trace.publishers import publish_llm_call, publish_final_output  # noqa: PLC0415

        publish_llm_call(
            step_id="step-1",
            turn=1,
            model="test-model",
            temperature=0.0,
            max_tokens=100,
            prompt_text="what is 2+2?",
            sections=[],
            response_text="4",
            tool_calls=[],
            stop_reason="end_turn",
            input_tokens=10,
            output_tokens=5,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            latency_ms=100,
        )
        publish_final_output(
            output_text="The answer is 4.",
            final_grade=None,
            judge_dimensions={},
        )

    # Session should be in DB (created via SessionStartEvent)
    session = tmp_db.get_session(session_id, include_messages=True)
    assert session is not None
    # At least the LLM call and final output messages should be present
    assert len(session.messages) >= 1


def test_finalize_persists_outcome_and_step_count(
    tmp_db: SessionDB,
    output_dir: Path,
) -> None:
    """finalize_session should update outcome and step_count after run ends."""
    session_id = "test-session-002"

    with TraceSession(
        session_id=session_id,
        level=1,
        level_label="test",
        input_query="count from 1 to 3",
        trace_mode="always",
        output_dir=output_dir,
        session_db=tmp_db,
    ) as ts:
        # Simulate a session that produces some LLM calls so summary builds cleanly
        from app.trace.publishers import publish_llm_call  # noqa: PLC0415

        for i in range(1, 4):
            publish_llm_call(
                step_id=f"step-{i}",
                turn=i,
                model="test-model",
                temperature=0.0,
                max_tokens=100,
                prompt_text=f"turn {i}",
                sections=[],
                response_text=str(i),
                tool_calls=[],
                stop_reason="end_turn",
                input_tokens=5 * i,
                output_tokens=2 * i,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                latency_ms=50,
            )
        ts.set_final_grade(None)

    session = tmp_db.get_session(session_id)
    assert session is not None
    # step_count and token totals should be non-zero
    assert session.step_count >= 1
    assert session.input_tokens > 0 or session.output_tokens > 0
