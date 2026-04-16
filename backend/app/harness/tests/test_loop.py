from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.clients.base import (
    CompletionResponse,
    ToolCall,
)
from app.harness.dispatcher import ToolDispatcher
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.loop import AgentLoop, LoopOutcome, _SYNTHESIS_SYSTEM, _SingleToolResult


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


def test_synthesis_system_contains_required_format_markers() -> None:
    """_SYNTHESIS_SYSTEM must enforce the three-section response format.

    When the agent goes silent and synthesis fires, the fallback prompt must
    still instruct the model to produce a Headline / Executive Summary /
    Evidence / Assumptions response — otherwise synthesis-triggered turns
    produce output that doesn't match the format expected by the frontend.
    """
    lowered = _SYNTHESIS_SYSTEM.lower()
    assert "headline" in lowered or "declarative" in lowered, \
        "_SYNTHESIS_SYSTEM must reference the Headline section"
    assert "executive summary" in lowered or "executive" in lowered, \
        "_SYNTHESIS_SYSTEM must reference the Executive Summary section"
    assert "evidence" in lowered, \
        "_SYNTHESIS_SYSTEM must reference the Evidence section"
    assert "assumptions" in lowered or "caveats" in lowered, \
        "_SYNTHESIS_SYSTEM must reference Assumptions & Caveats"
    assert "do not call any tools" in lowered or "no tools" in lowered, \
        "_SYNTHESIS_SYSTEM must tell the model not to call tools"


def test_dispatch_single_call_returns_single_tool_result() -> None:
    """_dispatch_single_call must return a _SingleToolResult with correct fields."""
    client = MagicMock()
    client.tier = "strict"

    disp = ToolDispatcher()
    disp.register("noop", lambda args: {"done": True})
    loop = AgentLoop(dispatcher=disp)

    from app.harness.turn_state import TurnState
    state = TurnState(dataset_loaded=False, scratchpad="")
    outcomes = []

    call = ToolCall(id="tc1", name="noop", arguments={"x": 1})
    result = loop._dispatch_single_call(call, state, outcomes, client)

    assert isinstance(result, _SingleToolResult)
    assert result.status == "ok"
    assert result.tool_message.role == "tool"
    assert result.tool_message.tool_use_id == "tc1"
    assert result.scratchpad_update is None
    assert result.todo_update is None
    assert result.is_a2a is False


def test_dispatch_single_call_records_tool_in_state() -> None:
    """_dispatch_single_call must update TurnState even when run outside run()."""
    from app.harness.turn_state import TurnState

    client = MagicMock()
    client.tier = "strict"
    disp = ToolDispatcher()
    disp.register("skill", lambda args: {"loaded": args.get("name", "")})
    loop = AgentLoop(dispatcher=disp)
    state = TurnState(dataset_loaded=False, scratchpad="")
    outcomes = []

    call = ToolCall(id="tc2", name="skill", arguments={"name": "correlation"})
    loop._dispatch_single_call(call, state, outcomes, client)

    trace = state.as_trace()
    assert any(evt["tool"] == "skill" for evt in trace), "tool must appear in state trace"


def test_run_and_run_stream_produce_same_tool_trace() -> None:
    """run() and run_stream() must leave TurnState in the same tool-trace shape."""
    def _make_client():
        return _client([
            CompletionResponse(
                text="",
                tool_calls=(ToolCall(id="t1", name="noop", arguments={}),),
                stop_reason="tool_use", usage={},
            ),
            CompletionResponse(text="done", tool_calls=(), stop_reason="end_turn", usage={}),
        ])

    disp_sync = ToolDispatcher()
    disp_sync.register("noop", lambda args: {"ok": True})
    loop_sync = AgentLoop(dispatcher=disp_sync)
    outcome_sync = loop_sync.run(
        client=_make_client(), system="sys", user_message="hi",
        dataset_loaded=False, max_steps=5,
    )

    disp_stream = ToolDispatcher()
    disp_stream.register("noop", lambda args: {"ok": True})
    loop_stream = AgentLoop(dispatcher=disp_stream)
    events = list(loop_stream.run_stream(
        client=_make_client(), system="sys", user_message="hi",
        dataset_loaded=False, max_steps=5,
    ))
    # Extract turn_end event to get final_text + stop_reason
    turn_end = next(e for e in events if e.type == "turn_end")

    assert outcome_sync.final_text == turn_end.payload["final_text"]
    assert outcome_sync.stop_reason == turn_end.payload["stop_reason"]

    # Both must have "noop" in their tool trace.
    sync_trace = outcome_sync.turn_state.as_trace()
    tool_names_sync = [evt["tool"] for evt in sync_trace]
    assert "noop" in tool_names_sync


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


