"""MCP Sampling Callbacks API (H6).

Provides a rate-limited HTTP endpoint for skills running inside the sandbox to
request lightweight model completions without going through the full AgentLoop.
Each session is capped at SAMPLING_LIMIT_PER_TURN calls to prevent runaway
token spend.

Rate-limit state is tracked per session_id in a module-level dict; it is
intentionally ephemeral (resets on restart) because sampling quotas only matter
within the lifetime of the current agent process.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.harness.turn_state import SAMPLING_LIMIT_PER_TURN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# ── Per-session sampling rate-limit counters ──────────────────────────────────

_counts_lock = threading.Lock()
_session_sampling_counts: dict[str, int] = {}


def _get_count(session_id: str) -> int:
    with _counts_lock:
        return _session_sampling_counts.get(session_id, 0)


def _increment_count(session_id: str) -> int:
    """Increment counter and return the *new* value."""
    with _counts_lock:
        new = _session_sampling_counts.get(session_id, 0) + 1
        _session_sampling_counts[session_id] = new
        return new


def reset_sampling_counts_for_tests() -> None:
    """Clear all counters.  Call from test fixtures only."""
    with _counts_lock:
        _session_sampling_counts.clear()


# ── Pydantic models ───────────────────────────────────────────────────────────


class SamplingRequest(BaseModel):
    session_id: str
    prompt: str
    max_tokens: int = 512
    system: str = ""


class SamplingResponse(BaseModel):
    text: str
    session_id: str
    sampling_call_index: int


# ── Dependency helpers ────────────────────────────────────────────────────────


def _get_model_client() -> Any:  # pragma: no cover
    """Return the default model client (late import keeps module lightweight)."""
    import anthropic  # noqa: PLC0415

    from app.harness.clients.anthropic_client import AnthropicClient  # noqa: PLC0415
    from app.harness.config import ModelProfile  # noqa: PLC0415

    profile = ModelProfile(
        name="mcp-sampler",
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        tier="standard",
    )
    return AnthropicClient(profile=profile, api_client=anthropic.Anthropic())


def _get_session_db() -> Any:  # pragma: no cover
    from app.harness.wiring import get_session_db  # noqa: PLC0415

    return get_session_db()


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post("/sample", response_model=SamplingResponse)
async def sample(body: SamplingRequest) -> SamplingResponse:
    """Request a lightweight model completion from a skill running in the sandbox.

    Rate-limited to ``SAMPLING_LIMIT_PER_TURN`` calls per session.  Returns 429
    when the limit is exceeded.
    """
    # Check current count before incrementing (pre-check prevents overshoot)
    current = _get_count(body.session_id)
    if current >= SAMPLING_LIMIT_PER_TURN:
        raise HTTPException(
            status_code=429,
            detail=(
                f"MCP sampling limit of {SAMPLING_LIMIT_PER_TURN} calls per session "
                "has been reached."
            ),
        )

    call_index = _increment_count(body.session_id)

    # Persist the sampling call to sessions.db so it shows in session history.
    try:
        db = _get_session_db()
        db.append_message(
            session_id=body.session_id,
            role="sampling",
            content=body.prompt[:2000],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not append sampling message to sessions.db: %s", exc)

    # Call the model.
    try:
        client = _get_model_client()
        messages = [{"role": "user", "content": body.prompt}]
        system = body.system or None
        response = client.complete(
            messages=messages,
            system=system,
            max_tokens=body.max_tokens,
        )
        text: str = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:  # noqa: BLE001
        logger.error("MCP sampling model call failed for session %s: %s", body.session_id, exc)
        raise HTTPException(status_code=500, detail=f"Model call failed: {exc}") from exc

    return SamplingResponse(
        text=text,
        session_id=body.session_id,
        sampling_call_index=call_index,
    )
