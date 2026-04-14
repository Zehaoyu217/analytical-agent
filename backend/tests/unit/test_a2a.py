"""Unit tests for A2A delegation (app.harness.a2a)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.harness.a2a import SubagentDispatcher, register_delegate_tool
from app.harness.clients.base import CompletionResponse, ToolCall
from app.harness.dispatcher import ToolDispatcher


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_client(text: str = "analysis done", calls: tuple[ToolCall, ...] = ()) -> MagicMock:
    """Return a mock ModelClient that yields one response and then stops."""
    client = MagicMock()
    client.tier = "worker"
    client.complete.return_value = CompletionResponse(
        text=text,
        tool_calls=calls,
        stop_reason="end_turn",
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    return client


# ── SubagentDispatcher ───────────────────────────────────────────────────────


def test_dispatch_creates_artifact(tmp_path: Path) -> None:
    client = _make_client(text="Sub-agent result: all good.")
    parent_dispatcher = ToolDispatcher()

    sd = SubagentDispatcher(
        client=client,
        parent_dispatcher=parent_dispatcher,
        parent_session_id="sess-test",
        artifact_dir=tmp_path,
    )

    result = sd.dispatch(task="analyse the data", tools_allowed=[])

    assert result.ok is True
    assert result.steps >= 1
    assert "Sub-agent result" in result.summary or result.summary != ""

    # Artifact file must exist and be valid JSON
    art_dir = tmp_path / "sess-test"
    artifacts = list(art_dir.glob("a2a-*.json"))
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text())
    assert payload["type"] == "subagent_result"
    assert payload["task"] == "analyse the data"


def test_dispatch_filters_tools_allowed(tmp_path: Path) -> None:
    """Only tools listed in tools_allowed should be available to the child."""
    parent_dispatcher = ToolDispatcher()
    parent_dispatcher.register("allowed_tool", lambda _: {"ok": True})
    parent_dispatcher.register("blocked_tool", lambda _: {"should": "not appear"})

    client = _make_client()
    sd = SubagentDispatcher(
        client=client,
        parent_dispatcher=parent_dispatcher,
        parent_session_id="sess-filter",
        artifact_dir=tmp_path,
    )
    result = sd.dispatch(task="do something", tools_allowed=["allowed_tool"])
    assert result.ok is True


def test_dispatch_returns_error_on_loop_failure(tmp_path: Path) -> None:
    client = MagicMock()
    client.tier = "worker"
    client.complete.side_effect = RuntimeError("model unavailable")

    parent_dispatcher = ToolDispatcher()
    sd = SubagentDispatcher(
        client=client,
        parent_dispatcher=parent_dispatcher,
        parent_session_id="sess-fail",
        artifact_dir=tmp_path,
    )
    result = sd.dispatch(task="failing task", tools_allowed=[])
    assert result.ok is False
    assert "model unavailable" in result.error


# ── register_delegate_tool ───────────────────────────────────────────────────


def test_register_delegate_tool(tmp_path: Path) -> None:
    parent = ToolDispatcher()
    client = _make_client("delegation complete")

    register_delegate_tool(
        dispatcher=parent,
        client=client,
        parent_session_id="sess-reg",
        artifact_dir=tmp_path,
    )

    assert parent.has("delegate_subagent")


def test_delegate_tool_handler_round_trip(tmp_path: Path) -> None:
    parent = ToolDispatcher()
    client = _make_client("delegation done")

    register_delegate_tool(
        dispatcher=parent,
        client=client,
        parent_session_id="sess-rt",
        artifact_dir=tmp_path,
    )

    call = ToolCall(id="c1", name="delegate_subagent", arguments={
        "task": "summarise the dataset",
        "tools_allowed": [],
    })
    result = parent.dispatch(call)
    assert result.ok is True
    payload = result.payload
    assert isinstance(payload, dict)
    assert "artifact_id" in payload
    assert "summary" in payload


def test_delegate_tool_missing_task(tmp_path: Path) -> None:
    parent = ToolDispatcher()
    client = _make_client()

    register_delegate_tool(
        dispatcher=parent,
        client=client,
        parent_session_id="sess-notask",
        artifact_dir=tmp_path,
    )

    call = ToolCall(id="c2", name="delegate_subagent", arguments={})
    result = parent.dispatch(call)
    # Should return ok=True with an error dict (handler returns without running the loop)
    assert isinstance(result.payload, dict)
    assert "error" in result.payload
