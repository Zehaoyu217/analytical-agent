"""Session search API — full-text search across past sessions via FTS5."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.harness.wiring import get_session_db
from app.storage.session_db import SearchResult

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SearchResultOut(dict):
    """Thin wrapper — results are returned as plain dicts for forward compatibility."""


@router.get("/search")
def search_sessions(
    q: str = Query(..., description="Search query", min_length=1),
    limit: int = Query(default=10, ge=1, le=20),
) -> list[dict]:
    """Full-text search across all past session messages.

    Returns up to `limit` results with: session_id, message_id, snippet, role, timestamp.
    """
    results: list[SearchResult] = get_session_db().search(query=q, limit=limit)
    return [
        {
            "session_id": r.session_id,
            "message_id": r.message_id,
            "snippet": r.snippet,
            "role": r.role,
            "timestamp": r.timestamp,
        }
        for r in results
    ]


@router.get("")
def list_sessions(
    source: str | None = Query(default=None, description="Filter by source: chat|cron|batch"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """List recent sessions, newest first."""
    sessions = get_session_db().list_sessions(limit=limit, source=source)
    return [
        {
            "id": s.id,
            "created_at": s.created_at,
            "model": s.model,
            "title": s.title,
            "goal": s.goal,
            "outcome": s.outcome,
            "source": s.source,
            "step_count": s.step_count,
            "input_tokens": s.input_tokens,
            "output_tokens": s.output_tokens,
        }
        for s in sessions
    ]


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    """Return a single session with its messages."""
    from fastapi import HTTPException  # noqa: PLC0415

    session = get_session_db().get_session(session_id, include_messages=True)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "id": session.id,
        "created_at": session.created_at,
        "model": session.model,
        "title": session.title,
        "goal": session.goal,
        "outcome": session.outcome,
        "source": session.source,
        "step_count": session.step_count,
        "input_tokens": session.input_tokens,
        "output_tokens": session.output_tokens,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_result": m.tool_result,
                "timestamp": m.timestamp,
                "step_index": m.step_index,
            }
            for m in session.messages
        ],
    }
