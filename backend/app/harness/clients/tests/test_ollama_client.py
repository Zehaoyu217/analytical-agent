from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.harness.clients.base import CompletionRequest, Message, ToolSchema
from app.harness.clients.ollama_client import OllamaClient
from app.harness.config import ModelProfile


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gemma_fast", provider="ollama",
        model_id="gemma4:26b", tier="strict",
        host="http://localhost:11434", num_ctx=16384,
        keep_alive="30m",
        options={"temperature": 0.3},
    )


def test_ollama_client_posts_and_parses_text_response() -> None:
    http = MagicMock()
    http.post.return_value.json.return_value = {
        "message": {"content": "hi back", "tool_calls": []},
        "done": True,
        "prompt_eval_count": 100,
        "eval_count": 20,
    }
    http.post.return_value.status_code = 200

    client = OllamaClient(profile=_profile(), http=http)
    resp = client.complete(CompletionRequest(
        system="sys",
        messages=(Message(role="user", content="hi"),),
        max_tokens=512,
    ))
    assert resp.text == "hi back"
    assert resp.stop_reason == "end_turn"
    args, kwargs = http.post.call_args
    assert args[0].endswith("/api/chat")
    payload = kwargs.get("json") or json.loads(kwargs.get("data", "{}"))
    assert payload["model"] == "gemma4:26b"
    assert payload["messages"][0]["role"] == "system"
    assert payload["options"]["num_ctx"] == 16384
    assert payload["options"]["temperature"] == 0.3


def test_ollama_client_surfaces_tool_calls() -> None:
    http = MagicMock()
    http.post.return_value.json.return_value = {
        "message": {
            "content": "",
            "tool_calls": [
                {"function": {"name": "skill", "arguments": {"name": "correlation"}}}
            ],
        },
        "done": True,
    }
    http.post.return_value.status_code = 200

    client = OllamaClient(profile=_profile(), http=http)
    resp = client.complete(CompletionRequest(
        system="", messages=(Message(role="user", content="hi"),),
        tools=(ToolSchema(name="skill", description="d", input_schema={"type": "object"}),),
        max_tokens=256,
    ))
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "skill"
    assert resp.tool_calls[0].arguments == {"name": "correlation"}
