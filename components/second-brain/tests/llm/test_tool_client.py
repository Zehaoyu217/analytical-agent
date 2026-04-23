from __future__ import annotations

import json

import httpx
import pytest

from second_brain.extract.schema import RECORD_CLAIMS_TOOL
from second_brain.llm.mlx_client import MLXResult
from second_brain.llm.providers import model_readiness, resolve_provider
from second_brain.llm.tool_client import ToolLLMClient, ToolLLMError


def test_resolve_provider_prefers_ollama_for_local_models() -> None:
    assert resolve_provider("ollama/gemma4:e4b", openrouter_key=None, anthropic_key=None) == "ollama"


def test_resolve_provider_supports_mlx_models() -> None:
    assert resolve_provider("mlx/mlx-community/gemma-3-4b-it-4bit", openrouter_key=None, anthropic_key=None) == "mlx"


def test_resolve_provider_prefers_openrouter_for_provider_qualified_models() -> None:
    assert resolve_provider(
        "openai/gpt-oss-120b:free",
        openrouter_key="or-key",
        anthropic_key=None,
    ) == "openrouter"


def test_model_readiness_checks_installed_ollama_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:11434/api/tags"
        return httpx.Response(200, json={"models": [{"name": "gemma4:e4b"}]})

    ok, reason = model_readiness(
        "ollama/gemma4:e4b",
        openrouter_key=None,
        anthropic_key=None,
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    assert reason == "ollama"


def test_model_readiness_accepts_installed_mlx_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("second_brain.llm.providers.importlib.util.find_spec", lambda _: object())
    ok, reason = model_readiness(
        "mlx/mlx-community/gemma-3-4b-it-4bit",
        openrouter_key=None,
        anthropic_key=None,
    )
    assert ok is True
    assert reason == "mlx"


def test_openrouter_tool_call_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-oss-120b:free",
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "record_claims",
                                        "arguments": json.dumps({"claims": [{"statement": "X"}]}),
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 15},
            },
        )

    client = ToolLLMClient(
        "openai/gpt-oss-120b:free",
        transport=httpx.MockTransport(handler),
    )
    result = client.call_tool(system="sys", user="user", tool=RECORD_CLAIMS_TOOL)

    assert result.tool_input == {"claims": [{"statement": "X"}]}
    assert result.tokens_in == 100
    assert result.tokens_out == 15
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    body = captured["body"]  # type: ignore[assignment]
    assert body["model"] == "openai/gpt-oss-120b:free"
    assert body["tool_choice"]["function"]["name"] == "record_claims"


def test_anthropic_tool_call_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthro-key")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "claude-opus-4-7",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "record_claims",
                        "input": {"claims": [{"statement": "Y"}]},
                    }
                ],
                "usage": {"input_tokens": 12, "output_tokens": 3},
            },
        )

    client = ToolLLMClient(
        "claude-opus-4-7",
        transport=httpx.MockTransport(handler),
    )
    result = client.call_tool(system="sys", user="user", tool=RECORD_CLAIMS_TOOL)
    assert result.tool_input == {"claims": [{"statement": "Y"}]}
    assert result.tokens_in == 12
    assert result.tokens_out == 3


def test_ollama_tool_call_parsing() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "gemma4:e4b",
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "record_claims",
                                "arguments": {"claims": [{"statement": "Z"}]},
                            }
                        }
                    ]
                },
                "prompt_eval_count": 20,
                "eval_count": 4,
            },
        )

    client = ToolLLMClient(
        "ollama/gemma4:e4b",
        transport=httpx.MockTransport(handler),
    )
    result = client.call_tool(system="sys", user="user", tool=RECORD_CLAIMS_TOOL)

    assert result.tool_input == {"claims": [{"statement": "Z"}]}
    assert result.tokens_in == 20
    assert result.tokens_out == 4
    assert captured["url"] == "http://localhost:11434/api/chat"
    body = captured["body"]  # type: ignore[assignment]
    assert body["model"] == "gemma4:e4b"


def test_mlx_tool_call_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "second_brain.llm.tool_client.complete_chat",
        lambda *args, **kwargs: MLXResult(
            text="<think>reasoning</think>\n```json\n{\"claims\":[{\"statement\":\"MLX works\"}]}\n```",
            tokens_in=41,
            tokens_out=8,
            model="mlx-community/gemma-3-4b-it-4bit",
        ),
    )
    client = ToolLLMClient("mlx/mlx-community/gemma-3-4b-it-4bit")
    result = client.call_tool(system="sys", user="user", tool=RECORD_CLAIMS_TOOL)
    assert result.tool_input == {"claims": [{"statement": "MLX works"}]}
    assert result.tokens_in == 41
    assert result.tokens_out == 8
    assert result.model == "mlx-community/gemma-3-4b-it-4bit"


def test_mlx_tool_call_retries_with_schema_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([
        MLXResult(
            text="I think the answer is probably about two claims.",
            tokens_in=10,
            tokens_out=5,
            model="mlx-community/gemma-3-4b-it-4bit",
        ),
        MLXResult(
            text='{"claims":[{"statement":"Retry works"}]}',
            tokens_in=12,
            tokens_out=6,
            model="mlx-community/gemma-3-4b-it-4bit",
        ),
    ])
    monkeypatch.setattr(
        "second_brain.llm.tool_client.complete_chat",
        lambda *args, **kwargs: next(responses),
    )
    client = ToolLLMClient("mlx/mlx-community/gemma-3-4b-it-4bit")
    result = client.call_tool(system="sys", user="user", tool=RECORD_CLAIMS_TOOL)
    assert result.tool_input == {"claims": [{"statement": "Retry works"}]}
    assert result.tokens_in == 12
    assert result.tokens_out == 6


def test_missing_tool_call_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {}}], "usage": {}})

    client = ToolLLMClient(
        "openai/gpt-oss-120b:free",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ToolLLMError, match="record_claims"):
        client.call_tool(system="sys", user="user", tool=RECORD_CLAIMS_TOOL)
