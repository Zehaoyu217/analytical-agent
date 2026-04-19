"""In-session todo tracking (P19).

The agent keeps a TodoWrite-style task list for the *current* session so the
human and the frontend can see what the agent has committed to, what's in
progress, and what remains.  Lives in memory and is scoped per session — the
next session starts with a fresh list.

Design
------
* ``TodoItem``: immutable record with ``id``, ``content``, ``status``.
* ``TodoStore``: thread-safe singleton keyed by ``session_id``.
* Writes *replace* the full list (matching Claude Code's TodoWrite pattern):
  the agent thinks about the whole plan each time, not incremental diffs.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from threading import RLock
from typing import Any, Literal

TodoStatus = Literal["pending", "in_progress", "completed"]
_VALID_STATUSES: frozenset[str] = frozenset(("pending", "in_progress", "completed"))


@dataclass(frozen=True, slots=True)
class TodoItem:
    id: str
    content: str
    status: TodoStatus

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "content": self.content, "status": self.status}


class TodoStore:
    """Thread-safe per-session todo storage."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_session: dict[str, tuple[TodoItem, ...]] = {}

    def list(self, session_id: str) -> tuple[TodoItem, ...]:
        with self._lock:
            return self._by_session.get(session_id, ())

    def replace(
        self, session_id: str, items: Sequence[dict[str, Any]]
    ) -> tuple[TodoItem, ...]:
        """Replace the session's todo list with ``items`` (list of dicts).

        Each dict must have ``id``, ``content``, ``status``.  Raises
        ``ValueError`` for malformed input — the agent sees this as a tool
        error and can correct on the next turn.
        """
        parsed = [_parse_item(item) for item in items]
        with self._lock:
            self._by_session[session_id] = tuple(parsed)
            return self._by_session[session_id]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._by_session.pop(session_id, None)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._by_session.clear()


def _parse_item(raw: object) -> TodoItem:
    if not isinstance(raw, dict):
        raise ValueError(f"todo item must be an object, got {type(raw).__name__}")
    tid = raw.get("id")
    content = raw.get("content")
    status = raw.get("status", "pending")
    if not isinstance(tid, str) or not tid.strip():
        raise ValueError("todo item missing non-empty 'id'")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"todo item {tid!r} missing non-empty 'content'")
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"todo item {tid!r} has invalid status {status!r};"
            f" allowed: {sorted(_VALID_STATUSES)}"
        )
    return TodoItem(id=tid.strip(), content=content.strip(), status=status)


_store = TodoStore()


def get_todo_store() -> TodoStore:
    """Process-wide singleton."""
    return _store
