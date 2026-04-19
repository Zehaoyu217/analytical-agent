from __future__ import annotations

from app.harness.clients.base import CompletionRequest, CompletionResponse, Message, ToolSchema


def test_message_is_frozen() -> None:
    import dataclasses

    import pytest
    m = Message(role="user", content="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.role = "system"  # type: ignore[misc]


def test_completion_response_surface() -> None:
    resp = CompletionResponse(
        text="ok",
        tool_calls=(),
        stop_reason="end_turn",
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    assert resp.text == "ok"
    assert resp.stop_reason == "end_turn"


def test_completion_request_tool_schema_list() -> None:
    req = CompletionRequest(
        system="you are",
        messages=(Message(role="user", content="hi"),),
        tools=(ToolSchema(name="skill", description="d",
                          input_schema={"type": "object"}),),
        max_tokens=1024,
    )
    assert len(req.tools) == 1
    assert req.tools[0].name == "skill"
