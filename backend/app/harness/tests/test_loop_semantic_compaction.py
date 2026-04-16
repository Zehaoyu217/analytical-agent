"""Stage-2 semantic compaction wiring (Phase 2 of Gap-Closure).

Verifies AgentLoop calls SemanticCompactor when wired AND the conversation
exceeds 80% of the configured token budget, and emits a ``semantic_compact``
StreamEvent in the streaming path.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.clients.base import CompletionResponse, Message
from app.harness.dispatcher import ToolDispatcher
from app.harness.loop import AgentLoop
from app.harness.semantic_compactor import (
    SemanticCompactionResult,
    SemanticCompactor,
)


def _client(text: str = "ok") -> MagicMock:
    client = MagicMock()
    client.name = "test"
    client.tier = "standard"
    client.complete.return_value = CompletionResponse(
        text=text, tool_calls=(), stop_reason="end_turn", usage={},
    )
    return client


def test_semantic_compactor_skipped_when_under_budget() -> None:
    sc = MagicMock(spec=SemanticCompactor)
    sc.should_compact.return_value = False

    loop = AgentLoop(
        dispatcher=ToolDispatcher(),
        semantic_compactor=sc,
        context_token_budget=200_000,
    )
    loop.run(
        client=_client(),
        system="sys",
        user_message="hi",
        dataset_loaded=False,
        max_steps=2,
    )
    sc.compact.assert_not_called()


def test_semantic_compactor_invoked_when_over_budget() -> None:
    sc = MagicMock(spec=SemanticCompactor)
    sc.should_compact.return_value = True
    sc.compact.return_value = SemanticCompactionResult(
        messages=[Message(role="user", content="compacted")],
        turns_summarized=4,
        tokens_before=900,
        tokens_after=200,
        summary_preview="summary preview",
    )

    loop = AgentLoop(
        dispatcher=ToolDispatcher(),
        semantic_compactor=sc,
        context_token_budget=200_000,
    )
    loop.run(
        client=_client(),
        system="sys",
        user_message="hi",
        dataset_loaded=False,
        max_steps=2,
    )
    sc.compact.assert_called_once()


def test_stream_emits_semantic_compact_event() -> None:
    sc = MagicMock(spec=SemanticCompactor)
    sc.should_compact.return_value = True
    sc.compact.return_value = SemanticCompactionResult(
        messages=[Message(role="user", content="compacted")],
        turns_summarized=3,
        tokens_before=800,
        tokens_after=300,
        summary_preview="prior turns summarized",
    )

    loop = AgentLoop(
        dispatcher=ToolDispatcher(),
        semantic_compactor=sc,
        context_token_budget=200_000,
    )
    events = list(loop.run_stream(
        client=_client(),
        system="sys",
        user_message="hi",
        dataset_loaded=False,
        session_id="s1",
        max_steps=2,
    ))
    semantic_events = [e for e in events if e.type == "semantic_compact"]
    assert len(semantic_events) == 1
    payload = semantic_events[0].payload
    assert payload["turns_summarized"] == 3
    assert payload["tokens_before"] == 800
    assert payload["tokens_after"] == 300
    assert payload["summary_preview"] == "prior turns summarized"


def test_loop_without_semantic_compactor_is_unchanged() -> None:
    loop = AgentLoop(dispatcher=ToolDispatcher())
    events = list(loop.run_stream(
        client=_client(),
        system="sys",
        user_message="hi",
        dataset_loaded=False,
        session_id="s1",
        max_steps=2,
    ))
    assert not any(e.type == "semantic_compact" for e in events)
