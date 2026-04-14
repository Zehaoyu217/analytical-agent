from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.clients.base import (
    CompletionResponse,
    ToolCall,
)
from app.harness.dispatcher import ToolDispatcher
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.loop import AgentLoop, LoopOutcome


def _client(responses: list[CompletionResponse]) -> MagicMock:
    client = MagicMock()
    client.name = "gemma_fast"
    client.tier = "strict"
    it = iter(responses)
    client.complete.side_effect = lambda req: next(it)
    return client


def test_loop_ends_on_end_turn_without_tool_calls() -> None:
    client = _client([
        CompletionResponse(text="all done", tool_calls=(),
                           stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(
        client=client,
        system="sys",
        user_message="hi",
        dataset_loaded=False,
        max_steps=4,
    )
    assert isinstance(outcome, LoopOutcome)
    assert outcome.final_text == "all done"
    assert outcome.steps == 1


def test_loop_dispatches_tool_and_feeds_result_back() -> None:
    client = _client([
        CompletionResponse(
            text="using tool",
            tool_calls=(ToolCall(id="t1", name="skill",
                                 arguments={"name": "correlation"}),),
            stop_reason="tool_use", usage={},
        ),
        CompletionResponse(text="done", tool_calls=(),
                           stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    disp.register("skill", lambda args: {"loaded": args["name"]})
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(client=client, system="sys", user_message="hi",
                       dataset_loaded=False, max_steps=5)
    assert outcome.steps == 2
    assert outcome.final_text == "done"
    assert any(evt["tool"] == "skill" for evt in outcome.turn_state.as_trace())


def test_loop_strict_tier_blocks_on_pre_tool_fail() -> None:
    client = _client([
        CompletionResponse(
            text="",
            tool_calls=(ToolCall(id="t1", name="promote_finding",
                                 arguments={"text": "X"}),),
            stop_reason="tool_use", usage={},
        ),
        CompletionResponse(text="forced end", tool_calls=(),
                           stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    disp.register("promote_finding", lambda args: {"ok": True})
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(
        client=client, system="sys", user_message="hi",
        dataset_loaded=True, max_steps=5,
    )
    # The block event should be visible in trace with status=blocked
    trace = outcome.turn_state.as_trace()
    blocked = [evt for evt in trace if evt.get("status") == "blocked"]
    assert blocked, "expected blocked pre_tool event"
    assert GuardrailOutcome.BLOCK in outcome.guardrail_outcomes


def test_loop_respects_max_steps() -> None:
    loop_response = CompletionResponse(
        text="", tool_calls=(ToolCall(id="t", name="noop", arguments={}),),
        stop_reason="tool_use", usage={},
    )
    client = _client([loop_response] * 10)
    disp = ToolDispatcher()
    disp.register("noop", lambda args: {"ok": True})
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(client=client, system="sys", user_message="go",
                       dataset_loaded=True, max_steps=3)
    assert outcome.steps == 3
    assert outcome.stop_reason == "max_steps"
