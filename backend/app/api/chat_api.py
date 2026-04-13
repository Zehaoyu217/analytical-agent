"""Chat endpoint — every conversation turn is wrapped in a TraceSession."""
from __future__ import annotations

import os
import re
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.trace.events import PromptSection
from app.trace.publishers import (
    TraceSession,
    publish_final_output,
    publish_llm_call,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MESSAGE_MAX_CHARS = 8000
_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MESSAGE_MAX_CHARS)
    session_id: str | None = Field(
        default=None,
        description="Frontend conversation id. If provided, new trace ids derive from it.",
    )


class ChatResponse(BaseModel):
    session_id: str
    response: str


def _traces_dir() -> Path:
    return Path(os.environ.get("TRACE_DIR", "traces"))


def _make_trace_id(conversation_id: str | None) -> str:
    timestamp = int(time.time() * 1000)
    nonce = secrets.token_hex(3)
    if conversation_id is None:
        return f"chat-{timestamp}-{nonce}"
    return f"{conversation_id}-{timestamp}-{nonce}"


def _generate_response(message: str) -> str:
    return (
        "You said: "
        + message
        + "\n\n(This is a stub response. Wire an LLM into app/api/chat_api.py to "
        "replace _generate_response.)"
    )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@router.post("")
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    conversation_id = payload.session_id
    if conversation_id is not None and not _CONVERSATION_ID_RE.match(conversation_id):
        raise HTTPException(status_code=400, detail="invalid session_id")

    trace_id = _make_trace_id(conversation_id)
    output_dir = _traces_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    with TraceSession(
        session_id=trace_id,
        level=1,
        level_label="chat",
        input_query=payload.message,
        trace_mode="always",
        output_dir=output_dir,
    ):
        response_text = _generate_response(payload.message)
        latency_ms = int((time.monotonic() - started) * 1000)

        publish_llm_call(
            step_id="s1",
            turn=1,
            model="stub-echo",
            temperature=0.0,
            max_tokens=1024,
            prompt_text=payload.message,
            sections=[
                PromptSection(
                    source="user_query",
                    lines="1-1",
                    text=payload.message,
                ),
            ],
            response_text=response_text,
            tool_calls=[],
            stop_reason="end_turn",
            input_tokens=_estimate_tokens(payload.message),
            output_tokens=_estimate_tokens(response_text),
            cache_read_tokens=0,
            cache_creation_tokens=0,
            latency_ms=latency_ms,
        )

        publish_final_output(
            output_text=response_text,
            final_grade=None,
            judge_dimensions={},
        )

    return ChatResponse(session_id=trace_id, response=response_text)
