from __future__ import annotations

import json

import httpx
import pytest

from second_brain.gardener.client import LLMClient, LLMError, LLMResult
from second_brain.llm.mlx_client import MLXResult


def _openrouter_response(text: str = "hi", prompt: int = 12, completion: int = 7) -> httpx.Response:
    body = {
        "model": "anthropic/claude-haiku-4-5",
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }
    return httpx.Response(200, json=body)


def _anthropic_response(text: str = "ok", tin: int = 4, tout: int = 2) -> httpx.Response:
    body = {
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": tin, "output_tokens": tout},
    }
    return httpx.Response(200, json=body)


def test_openrouter_payload_and_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return _openrouter_response("hello world", prompt=100, completion=25)

    transport = httpx.MockTransport(handler)
    client = LLMClient("anthropic/claude-haiku-4-5", transport=transport)
    result = client.complete("sys", "user msg", max_tokens=256, temperature=0.2)

    assert isinstance(result, LLMResult)
    assert result.text == "hello world"
    assert result.tokens_in == 100
    assert result.tokens_out == 25
    assert result.model == "anthropic/claude-haiku-4-5"

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    headers = captured["headers"]  # type: ignore[assignment]
    assert headers["authorization"] == "Bearer test-or-key"
    body = captured["body"]  # type: ignore[assignment]
    assert body["model"] == "anthropic/claude-haiku-4-5"
    assert body["max_tokens"] == 256
    assert body["temperature"] == 0.2
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user msg"},
    ]


def test_ollama_payload_and_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "gemma4:e4b",
                "message": {"content": "local answer"},
                "prompt_eval_count": 31,
                "eval_count": 9,
            },
        )

    transport = httpx.MockTransport(handler)
    client = LLMClient("ollama/gemma4:e4b", transport=transport)
    result = client.complete("sys", "user msg", max_tokens=128, temperature=0.1)

    assert result.text == "local answer"
    assert result.tokens_in == 31
    assert result.tokens_out == 9
    assert result.model == "gemma4:e4b"
    assert captured["url"] == "http://localhost:11434/api/chat"
    body = captured["body"]  # type: ignore[assignment]
    assert body["model"] == "gemma4:e4b"
    assert body["options"]["num_predict"] == 128
    assert body["options"]["temperature"] == 0.1


def test_mlx_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "second_brain.gardener.client.complete_chat",
        lambda *args, **kwargs: MLXResult(
            text="local mlx answer",
            tokens_in=33,
            tokens_out=12,
            model="mlx-community/gemma-3-4b-it-4bit",
        ),
    )
    client = LLMClient("mlx/mlx-community/gemma-3-4b-it-4bit")
    result = client.complete("sys", "user msg", max_tokens=128, temperature=0.1)
    assert result.text == "local mlx answer"
    assert result.tokens_in == 33
    assert result.tokens_out == 12
    assert result.model == "mlx-community/gemma-3-4b-it-4bit"


def test_anthropic_fallback_when_no_openrouter_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return _anthropic_response("answer", tin=40, tout=9)

    transport = httpx.MockTransport(handler)
    client = LLMClient("anthropic/claude-haiku-4-5", transport=transport)
    result = client.complete("sysprompt", "question")

    assert result.text == "answer"
    assert result.tokens_in == 40
    assert result.tokens_out == 9

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    headers = captured["headers"]  # type: ignore[assignment]
    assert headers["x-api-key"] == "test-anthropic-key"
    assert headers["anthropic-version"] == "2023-06-01"
    body = captured["body"]  # type: ignore[assignment]
    # Vendor prefix stripped for native API.
    assert body["model"] == "claude-haiku-4-5"
    assert body["system"] == "sysprompt"
    assert body["messages"] == [{"role": "user", "content": "question"}]


def test_missing_keys_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LLMClient("openai/gpt-oss-120b:free")
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        client.complete("s", "u")


def test_anthropic_only_used_for_anthropic_models(monkeypatch: pytest.MonkeyPatch) -> None:
    # No OpenRouter key, anthropic key present, but the model is openai/*.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthro-key")
    client = LLMClient("openai/gpt-4o-mini")
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        client.complete("s", "u")


def test_http_error_status_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream boom")

    transport = httpx.MockTransport(handler)
    client = LLMClient("anthropic/claude-haiku-4-5", transport=transport)
    with pytest.raises(LLMError, match="500"):
        client.complete("s", "u")


def test_malformed_openrouter_body_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    transport = httpx.MockTransport(handler)
    client = LLMClient("anthropic/claude-haiku-4-5", transport=transport)
    with pytest.raises(LLMError, match="malformed"):
        client.complete("s", "u")


def test_transport_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    transport = httpx.MockTransport(handler)
    client = LLMClient("anthropic/claude-haiku-4-5", transport=transport)
    with pytest.raises(LLMError, match="transport error"):
        client.complete("s", "u")
