"""REST endpoints for chat conversation persistence.

Storage layout: one JSON file per conversation at `data/conversations/{id}.json`
(`DATA_DIR` env var overrides the base). Single-process assumption — no
cross-process locking is attempted; atomic writes protect against partial
writes within a single process.
"""
from __future__ import annotations

import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.storage.json_store import JsonStoreError, read_json, write_json_atomic

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CONTENT_MAX = 100_000
_TITLE_MAX = 200

# Per-conversation locks serialize read-modify-write on append-turn, preventing
# lost updates when concurrent requests hit the same conversation. Uvicorn runs
# sync handlers on a thread pool so this is reachable in the happy path.
_LOCK_REGISTRY_GUARD = threading.Lock()
_CONV_LOCKS: dict[str, threading.Lock] = {}


def _conv_lock(conv_id: str) -> threading.Lock:
    with _LOCK_REGISTRY_GUARD:
        lock = _CONV_LOCKS.get(conv_id)
        if lock is None:
            lock = threading.Lock()
            _CONV_LOCKS[conv_id] = lock
        return lock


class ConversationTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=_CONTENT_MAX)
    timestamp: float  # unix epoch seconds


class TurnCreate(BaseModel):
    """Incoming turn — server fills the timestamp."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=_CONTENT_MAX)


class Conversation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    created_at: float
    updated_at: float
    turns: list[ConversationTurn]


class ConversationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    created_at: float
    updated_at: float
    turn_count: int


class ConversationCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(..., min_length=1, max_length=_TITLE_MAX)


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))


def _conversations_dir() -> Path:
    return _data_dir() / "conversations"


def _validate_id(conv_id: str) -> None:
    if not _CONVERSATION_ID_RE.match(conv_id):
        raise HTTPException(status_code=400, detail="invalid conversation id")


def _conv_path(conv_id: str) -> Path:
    return _conversations_dir() / f"{conv_id}.json"


def _load_or_404(conv_id: str) -> Conversation:
    _validate_id(conv_id)
    path = _conv_path(conv_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="conversation not found")
    try:
        return read_json(path, Conversation)
    except JsonStoreError as exc:
        raise HTTPException(status_code=500, detail="failed to load conversation") from exc


def _new_id() -> str:
    # 24 hex chars — matches the spec "id = 24-hex".
    return secrets.token_hex(12)


@router.get("")
def list_conversations() -> list[ConversationSummary]:
    conv_dir = _conversations_dir()
    if not conv_dir.exists():
        return []
    summaries: list[ConversationSummary] = []
    for path in conv_dir.glob("*.json"):
        try:
            conv = read_json(path, Conversation)
        except JsonStoreError:
            # Skip corrupt files; don't let one bad entry break the list.
            continue
        summaries.append(
            ConversationSummary(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                turn_count=len(conv.turns),
            )
        )
    return sorted(summaries, key=lambda s: s.updated_at, reverse=True)


@router.post("")
def create_conversation(payload: ConversationCreate) -> Conversation:
    now = time.time()
    conv = Conversation(
        id=_new_id(),
        title=payload.title,
        created_at=now,
        updated_at=now,
        turns=[],
    )
    write_json_atomic(_conv_path(conv.id), conv)
    return conv


@router.get("/{conv_id}")
def get_conversation(conv_id: str) -> Conversation:
    return _load_or_404(conv_id)


@router.post("/{conv_id}/turns")
def append_turn(conv_id: str, payload: TurnCreate) -> Conversation:
    _validate_id(conv_id)
    with _conv_lock(conv_id):
        conv = _load_or_404(conv_id)
        turn = ConversationTurn(
            role=payload.role,
            content=payload.content,
            timestamp=time.time(),
        )
        updated = Conversation(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=turn.timestamp,
            turns=[*conv.turns, turn],
        )
        write_json_atomic(_conv_path(conv_id), updated)
        return updated


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str) -> dict[str, object]:
    _validate_id(conv_id)
    with _conv_lock(conv_id):
        path = _conv_path(conv_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="conversation not found")
        path.unlink()
        with _LOCK_REGISTRY_GUARD:
            _CONV_LOCKS.pop(conv_id, None)
        return {"ok": True}
