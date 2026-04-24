"""Transient-error handling in OpenRouterClient.

OpenRouter's free tier routinely surfaces upstream 503 ("no healthy upstream")
for individual model/provider combos. The client retries once, then raises
RateLimitError so the FallbackModelClient chain can take over.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.harness.clients.base import (
    CompletionRequest,
    Message,
    RateLimitError,
)
from app.harness.clients.openrouter_client import OpenRouterClient
from app.harness.config import ModelProfile


def _profile() -> ModelProfile:
    return ModelProfile(
        name="test",
        provider="openrouter",
        model_id="openai/gpt-oss-120b:free",
        tier="observatory",
        host="https://openrouter.ai/api/v1",
        options={"api_key": "test-key"},
    )


def _req() -> CompletionRequest:
    return CompletionRequest(
        system="",
        messages=(Message(role="user", content="hi"),),
        max_tokens=10,
    )


def _resp(status_code: int, body: dict | None = None, text: str = "") -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = body or {}
    m.text = text
    return m


def test_503_retries_once_then_succeeds(monkeypatch) -> None:
    """Transient 503 followed by a 200 should return the 200 payload."""
    monkeypatch.setattr(
        "app.harness.clients.openrouter_client.time.sleep",
        lambda _s: None,  # skip the retry delay in tests
    )
    http = MagicMock()
    http.post.side_effect = [
        _resp(503, text="no healthy upstream"),
        _resp(200, {
            "choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }),
    ]

    client = OpenRouterClient(_profile(), http)
    resp = client.complete(_req())
    assert resp.text == "pong"
    assert http.post.call_count == 2


def test_503_twice_raises_rate_limit_error(monkeypatch) -> None:
    """Two consecutive 503s should bubble as RateLimitError so the fallback chain engages."""
    monkeypatch.setattr(
        "app.harness.clients.openrouter_client.time.sleep",
        lambda _s: None,
    )
    http = MagicMock()
    http.post.return_value = _resp(503, text="no healthy upstream")

    client = OpenRouterClient(_profile(), http)
    with pytest.raises(RateLimitError) as exc:
        client.complete(_req())
    assert "upstream unhealthy" in str(exc.value)
    assert http.post.call_count == 2


def test_502_also_treated_as_transient(monkeypatch) -> None:
    """Any of the transient-status family retries the same way."""
    monkeypatch.setattr(
        "app.harness.clients.openrouter_client.time.sleep",
        lambda _s: None,
    )
    http = MagicMock()
    http.post.side_effect = [
        _resp(502, text="bad gateway"),
        _resp(200, {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {},
        }),
    ]
    client = OpenRouterClient(_profile(), http)
    resp = client.complete(_req())
    assert resp.text == "ok"
    assert http.post.call_count == 2


def test_429_still_raises_immediately() -> None:
    """429 is a hard rate-limit — no retry, go straight to fallback chain."""
    http = MagicMock()
    http.post.return_value = _resp(429, text="too many requests")
    client = OpenRouterClient(_profile(), http)
    with pytest.raises(RateLimitError):
        client.complete(_req())
    assert http.post.call_count == 1


def test_500_still_raises_runtime_error() -> None:
    """Non-transient 5xx (500) should not retry — it's a real bug."""
    http = MagicMock()
    http.post.return_value = _resp(500, text="internal error")
    client = OpenRouterClient(_profile(), http)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        client.complete(_req())
    assert http.post.call_count == 1
