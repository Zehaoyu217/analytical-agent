from __future__ import annotations

import threading
from unittest.mock import MagicMock

from app.harness.clients.base import (
    CompletionResponse,
    ToolCall,
)
from app.harness.dispatcher import ToolDispatcher
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.loop import (
    NEVER_PARALLEL_TOOLS,
    PARALLEL_SAFE_TOOLS,
    AgentLoop,
    LoopOutcome,
    _should_parallelize,
)


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


# ── _should_parallelize ───────────────────────────────────────────────────────

def test_should_parallelize_true_for_two_safe_tools() -> None:
    calls = [
        ToolCall(id="a", name="skill", arguments={}),
        ToolCall(id="b", name="execute_python", arguments={}),
    ]
    assert _should_parallelize(calls) is True


def test_should_parallelize_false_for_single_call() -> None:
    calls = [ToolCall(id="a", name="skill", arguments={})]
    assert _should_parallelize(calls) is False


def test_should_parallelize_false_when_any_never_parallel() -> None:
    calls = [
        ToolCall(id="a", name="skill", arguments={}),
        ToolCall(id="b", name="write_working", arguments={}),
    ]
    assert _should_parallelize(calls) is False


def test_should_parallelize_false_for_unknown_tool() -> None:
    calls = [
        ToolCall(id="a", name="skill", arguments={}),
        ToolCall(id="b", name="unknown_tool", arguments={}),
    ]
    assert _should_parallelize(calls) is False


def test_parallel_safe_and_never_parallel_are_disjoint() -> None:
    assert PARALLEL_SAFE_TOOLS.isdisjoint(NEVER_PARALLEL_TOOLS)


# ── Parallel dispatch ─────────────────────────────────────────────────────────

def test_loop_dispatches_parallel_safe_tools_concurrently() -> None:
    """Two parallel-safe tools should be dispatched concurrently (both results appear)."""
    call_thread_ids: list[int] = []
    lock = threading.Lock()

    def handler(args: dict) -> dict:
        with lock:
            call_thread_ids.append(threading.get_ident())
        return {"done": True}

    client = _client([
        CompletionResponse(
            text="",
            tool_calls=(
                ToolCall(id="t1", name="execute_python", arguments={"code": "1+1"}),
                ToolCall(id="t2", name="execute_python", arguments={"code": "2+2"}),
            ),
            stop_reason="tool_use", usage={},
        ),
        CompletionResponse(text="done", tool_calls=(), stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    disp.register("execute_python", handler)
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(client=client, system="sys", user_message="go",
                       dataset_loaded=True, max_steps=5)
    assert outcome.final_text == "done"
    # Both tools were dispatched
    assert len(call_thread_ids) == 2


def test_loop_dynamic_ctx_prepended_to_user_message() -> None:
    """When injector_inputs yields dynamic ctx, it is merged into user_message."""
    captured_messages: list = []

    def capture_and_respond(req):
        captured_messages.append(list(req.messages))
        return CompletionResponse(text="ok", tool_calls=(), stop_reason="end_turn", usage={})

    client = MagicMock()
    client.name = "test"
    client.tier = "strict"
    client.complete.side_effect = capture_and_respond

    # Build a minimal injector that returns known static/dynamic content
    injector = MagicMock()
    injector.build_static.return_value = "STATIC_SYSTEM"
    injector.build_dynamic.return_value = "DYNAMIC_CONTEXT"

    injector_inputs = MagicMock()

    disp = ToolDispatcher()
    loop = AgentLoop(dispatcher=disp)
    loop.run(
        client=client,
        system="ignored",
        user_message="hello",
        dataset_loaded=False,
        injector=injector,
        injector_inputs=injector_inputs,
    )

    assert captured_messages, "No LLM call made"
    first_req_messages = captured_messages[0]
    first_user_msg = first_req_messages[0]
    assert first_user_msg.role == "user"
    assert "DYNAMIC_CONTEXT" in first_user_msg.content
    assert "hello" in first_user_msg.content
