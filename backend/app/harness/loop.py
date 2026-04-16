from __future__ import annotations

import json
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
    ToolCall,
    ToolSchema,
)
from app.harness.compactor import MicroCompactor
from app.harness.dispatcher import ToolDispatcher, ToolResult
from app.harness.hooks import HookRunner
from app.harness.guardrails.end_of_turn import end_of_turn
from app.harness.guardrails.post_tool import post_tool
from app.harness.guardrails.pre_tool import pre_tool_gate
from app.harness.guardrails.tiers import apply_tier
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.stream_events import StreamEvent
from app.harness.turn_state import TurnState

if TYPE_CHECKING:
    from app.harness.injector import InjectorInputs, PreTurnInjector

# ── Parallel tool execution policy ────────────────────────────────────────────

# Tools that are safe to dispatch concurrently: read-only or fully isolated.
PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset({
    "skill",
    "sandbox.run",
    "execute_python",
    "session_search",
})

# Tools that must never run concurrently: they mutate shared state.
NEVER_PARALLEL_TOOLS: frozenset[str] = frozenset({
    "delegate_subagent",
    "write_working",
    "promote_finding",
    "save_artifact",
    "todo_write",
    "todo_read",
})


def _should_parallelize(calls: list[ToolCall]) -> bool:
    """Return True when every call in the batch is safe to run concurrently."""
    return (
        len(calls) >= 2
        and all(c.name in PARALLEL_SAFE_TOOLS for c in calls)
        and not any(c.name in NEVER_PARALLEL_TOOLS for c in calls)
    )


@dataclass
class LoopOutcome:
    final_text: str
    steps: int
    stop_reason: str
    turn_state: TurnState
    guardrail_outcomes: list[GuardrailOutcome] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        dispatcher: ToolDispatcher,
        compactor: MicroCompactor | None = None,
        hook_runner: HookRunner | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._compactor = compactor or MicroCompactor()
        self._hook_runner = hook_runner or HookRunner()

    def run(
        self,
        client: ModelClient,
        system: str,
        user_message: str,
        dataset_loaded: bool,
        max_steps: int = 12,
        scratchpad: str = "",
        tools: tuple[ToolSchema, ...] = (),
        injector: PreTurnInjector | None = None,
        injector_inputs: InjectorInputs | None = None,
    ) -> LoopOutcome:
        # Build static system prompt from injector when provided (cache-preservation).
        if injector is not None:
            system = injector.build_static()

        # Merge per-turn dynamic context into the initial user message.
        # Must be prepended to the message content — NOT a separate user message,
        # because the Anthropic API rejects consecutive user-role entries.
        if injector is not None and injector_inputs is not None:
            dynamic_ctx = injector.build_dynamic(injector_inputs)
            if dynamic_ctx:
                user_message = f"{dynamic_ctx}\n\n{user_message}"

        state = TurnState(dataset_loaded=dataset_loaded, scratchpad=scratchpad)
        messages: list[Message] = [Message(role="user", content=user_message)]
        outcomes: list[GuardrailOutcome] = []
        final_text = ""
        steps = 0
        stop_reason = "end_turn"
        _synthesis_injected = False  # True after we inject a synthesis prompt

        for step in range(1, max_steps + 1):
            steps = step
            messages, _ = self._compactor.maybe_compact(messages)
            # Force tool use on the first step when no tool results are in context yet.
            # After a synthesis prompt is injected, strip tools so the model MUST write text.
            has_tool_results = any(m.role == "tool" for m in messages)
            if _synthesis_injected:
                # Fresh minimal context for synthesis — avoids free-model context overflow.
                req_messages = _build_synthesis_messages(user_message, messages)
                req_tools: tuple[ToolSchema, ...] = ()
                req_tool_choice = None
            elif tools and not has_tool_results:
                req_messages = messages
                req_tools = tools
                req_tool_choice = "required"
            else:
                req_messages = messages
                req_tools = tools
                req_tool_choice = None
            # On synthesis retry use a minimal system prompt so the model doesn't
            # follow "always use tools" instructions from the full data-analyst prompt.
            req_system = _SYNTHESIS_SYSTEM if _synthesis_injected else system
            resp = client.complete(CompletionRequest(
                system=req_system, messages=tuple(req_messages),
                tools=req_tools, max_tokens=4096,
                tool_choice=req_tool_choice,
            ))
            final_text = resp.text

            if not resp.tool_calls:
                # If the model went silent after making tool calls, inject a synthesis
                # prompt once and retry — this time with a fresh minimal context.
                if (
                    not final_text.strip()
                    and has_tool_results
                    and not _synthesis_injected
                    and steps < max_steps
                ):
                    _synthesis_injected = True
                    continue
                stop_reason = resp.stop_reason or "end_turn"
                break

            _synthesis_injected = False  # reset if model made tool calls
            messages.append(Message(
                role="assistant",
                content=resp.text or "",
                tool_calls=tuple(resp.tool_calls),
            ))

            # ── Phase 1: Pre-gate and pre-hooks ───────────────────────────────
            _scheduled: list[ToolCall] = []
            for call in resp.tool_calls:
                pre_findings = pre_tool_gate(
                    call, turn_trace=state.as_trace(),
                    dataset_loaded=state.dataset_loaded,
                )
                pre_outcome = apply_tier(client.tier, pre_findings)
                outcomes.append(pre_outcome)
                if pre_outcome is GuardrailOutcome.BLOCK:
                    state.record_tool(
                        name=call.name,
                        result_payload={
                            "error": "blocked_by_pre_tool_gate",
                            "findings": [f.code for f in pre_findings],
                        },
                        status="blocked",
                    )
                    messages.append(Message(
                        role="tool", tool_use_id=call.id,
                        name=call.name,
                        content=json.dumps({
                            "blocked": True,
                            "reasons": [f.message for f in pre_findings],
                        }),
                    ))
                    continue
                self._hook_runner.run_pre(call.name, call.arguments)
                _scheduled.append(call)

            # ── Phase 2: Dispatch (parallel or sequential) ────────────────────
            _results: dict[str, ToolResult] = {}
            if _should_parallelize(_scheduled):
                with ThreadPoolExecutor(max_workers=len(_scheduled)) as pool:
                    for call, result in zip(
                        _scheduled, pool.map(self._dispatcher.dispatch, _scheduled)
                    ):
                        _results[call.id] = result
            else:
                for call in _scheduled:
                    _results[call.id] = self._dispatcher.dispatch(call)

            # ── Phase 3: Post-process ─────────────────────────────────────────
            for call in _scheduled:
                result = _results[call.id]
                self._hook_runner.run_post(
                    call.name,
                    result.payload if isinstance(result.payload, dict) else {},
                )
                report = post_tool(result)
                for aid in report.new_artifact_ids:
                    state.record_artifact(aid)
                if call.name == "write_working" and result.ok:
                    new_pad = (result.payload or {}).get("content", "")
                    if new_pad:
                        state.scratchpad = new_pad
                state.record_tool(
                    name=call.name,
                    result_payload=(result.payload
                                    if isinstance(result.payload, dict) else
                                    {"value": result.payload}),
                    status="ok" if result.ok else "error",
                )
                content = json.dumps(_serializable(result.payload))
                if report.trimmed_stdout:
                    content = json.dumps({
                        "artifact_refs": list(report.new_artifact_ids),
                        "trimmed_preview": report.trimmed_stdout,
                    })
                messages.append(Message(
                    role="tool", tool_use_id=call.id,
                    name=call.name, content=content,
                ))
        else:
            stop_reason = "max_steps"

        end_findings = end_of_turn(
            scratchpad=state.scratchpad,
            claims=[],  # claim extraction handled by TurnWrapUp when it parses final_text
        )
        outcomes.append(apply_tier(client.tier, end_findings))

        return LoopOutcome(
            final_text=final_text, steps=steps,
            stop_reason=stop_reason, turn_state=state,
            guardrail_outcomes=outcomes,
        )

    def run_stream(
        self,
        client: ModelClient,
        system: str,
        user_message: str,
        dataset_loaded: bool,
        session_id: str = "",
        max_steps: int = 12,
        scratchpad: str = "",
        tools: tuple[ToolSchema, ...] = (),
        injector: PreTurnInjector | None = None,
        injector_inputs: InjectorInputs | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Run the agent loop, yielding a StreamEvent for each notable moment.

        Yields turn_start before each LLM call, tool_call / tool_result around
        each dispatch, and turn_end when the loop exits.  Callers can serialise
        each event to SSE via ``event.to_sse()``.

        A ``scratchpad_delta`` event is emitted whenever the agent calls the
        ``write_working`` tool, carrying the full new scratchpad content so the
        UI can show live reasoning.

        When *injector* is provided, the static system prompt is built via
        ``build_static()`` (overriding the *system* parameter) and per-turn
        dynamic context is merged into the initial user message before the first
        LLM call, preserving Anthropic's prompt-cache prefix.
        """
        # Build static system prompt from injector when provided (cache-preservation).
        if injector is not None:
            system = injector.build_static()

        # Merge per-turn dynamic context into the initial user message.
        # Must be prepended to the message content — NOT a separate user message,
        # because the Anthropic API rejects consecutive user-role entries.
        if injector is not None and injector_inputs is not None:
            dynamic_ctx = injector.build_dynamic(injector_inputs)
            if dynamic_ctx:
                user_message = f"{dynamic_ctx}\n\n{user_message}"

        state = TurnState(dataset_loaded=dataset_loaded, scratchpad=scratchpad)
        messages: list[Message] = [Message(role="user", content=user_message)]
        outcomes: list[GuardrailOutcome] = []
        final_text = ""
        steps = 0
        stop_reason = "end_turn"
        _synthesis_injected = False  # True after we inject a synthesis prompt

        for steps in range(1, max_steps + 1):
            yield StreamEvent(
                type="turn_start",
                payload={"session_id": session_id, "step": steps},
            )

            messages, compact_report = self._compactor.maybe_compact(messages)
            if compact_report.triggered:
                yield StreamEvent(
                    type="micro_compact",
                    payload={
                        "step": steps,
                        "dropped_messages": compact_report.dropped_messages,
                        "chars_before": compact_report.chars_before,
                        "chars_after": compact_report.chars_after,
                        "tokens_before": compact_report.tokens_before,
                        "tokens_after": compact_report.tokens_after,
                        "artifact_refs": list(compact_report.artifact_refs),
                    },
                )

            _llm_start = time.monotonic()
            # Force tool use on the first step when no tool results are in context yet.
            # After a synthesis prompt is injected, use a fresh minimal context to avoid
            # free-model context overflow causing silent empty responses.
            has_tool_results = any(m.role == "tool" for m in messages)
            if _synthesis_injected:
                req_messages = _build_synthesis_messages(user_message, messages)
                req_tools: tuple[ToolSchema, ...] = ()
                req_tool_choice = None
            elif tools and not has_tool_results:
                req_messages = messages
                req_tools = tools
                req_tool_choice = "required"
            else:
                req_messages = messages
                req_tools = tools
                req_tool_choice = None
            # On synthesis retry use a minimal system prompt so the model doesn't
            # follow "always use tools" instructions from the full data-analyst prompt.
            req_system = _SYNTHESIS_SYSTEM if _synthesis_injected else system
            resp = client.complete(CompletionRequest(
                system=req_system, messages=tuple(req_messages),
                tools=req_tools, max_tokens=4096,
                tool_choice=req_tool_choice,
            ))
            _llm_ms = int((time.monotonic() - _llm_start) * 1000)
            final_text = resp.text

            # ── Per-turn LLM call trace event ─────────────────────────────
            # Also yield a debug_step stream event so the eval adapter can log
            # per-step outcomes without needing to inspect backend logs.
            yield StreamEvent(
                type="debug_step",
                payload={
                    "step": steps,
                    "synthesis": _synthesis_injected,
                    "tool_choice": req_tool_choice,
                    "n_req_msgs": len(req_messages),
                    "n_tools": len(req_tools),
                    "resp_len": len(final_text or ""),
                    "resp_tool_calls": len(resp.tool_calls),
                    "stop_reason": resp.stop_reason,
                    "input_tokens": resp.usage.get("input_tokens", 0),
                    "output_tokens": resp.usage.get("output_tokens", 0),
                    "latency_ms": _llm_ms,
                },
            )
            try:
                from app.trace.events import PromptSection
                from app.trace.publishers import publish_llm_call as _pub_llm
                _prompt_text = "\n\n".join(
                    f"[{m.role.upper()}]: {m.content or ''}" for m in req_messages
                )
                _pub_llm(
                    step_id=f"s{steps}",
                    turn=steps,
                    model=getattr(client, "name", "unknown"),
                    temperature=0.0,
                    max_tokens=2048,
                    prompt_text=_prompt_text[:4096],
                    sections=[
                        PromptSection(source="system_prompt", lines="1-1", text=system[:2048]),
                        PromptSection(source="user_query", lines="1-1", text=_prompt_text[:2048]),
                    ],
                    response_text=(resp.text or "")[:4096],
                    tool_calls=[
                        {"name": tc.name, "input": tc.arguments}
                        for tc in (resp.tool_calls or [])
                    ],
                    stop_reason=resp.stop_reason or "end_turn",
                    input_tokens=resp.usage.get("input_tokens", 0),
                    output_tokens=resp.usage.get("output_tokens", 0),
                    cache_read_tokens=resp.usage.get("cache_read_input_tokens", 0),
                    cache_creation_tokens=resp.usage.get("cache_creation_input_tokens", 0),
                    latency_ms=_llm_ms,
                )
            except Exception:  # noqa: BLE001 — trace must never crash the loop
                pass

            if not resp.tool_calls:
                # If the model went silent after making tool calls, retry once using a
                # fresh minimal context (_build_synthesis_messages) so free models aren't
                # overwhelmed by the full bloated conversation history.
                if (
                    not final_text.strip()
                    and has_tool_results
                    and not _synthesis_injected
                    and steps < max_steps
                ):
                    _synthesis_injected = True
                    continue
                stop_reason = resp.stop_reason or "end_turn"
                break

            _synthesis_injected = False  # reset if model made tool calls
            messages.append(Message(
                role="assistant",
                content=resp.text or "",
                tool_calls=tuple(resp.tool_calls),
            ))

            # ── Phase 1: Pre-gate, pre-hooks, and streaming tool_call events ──
            _scheduled: list[ToolCall] = []
            _a2a_calls: set[str] = set()

            for call in resp.tool_calls:
                yield StreamEvent(
                    type="tool_call",
                    payload={
                        "step": steps,
                        "name": call.name,
                        "input_preview": _arg_preview(call.arguments),
                    },
                )

                pre_findings = pre_tool_gate(
                    call, turn_trace=state.as_trace(),
                    dataset_loaded=state.dataset_loaded,
                )
                pre_outcome = apply_tier(client.tier, pre_findings)
                outcomes.append(pre_outcome)

                if pre_outcome is GuardrailOutcome.BLOCK:
                    state.record_tool(
                        name=call.name,
                        result_payload={
                            "error": "blocked_by_pre_tool_gate",
                            "findings": [f.code for f in pre_findings],
                        },
                        status="blocked",
                    )
                    messages.append(Message(
                        role="tool", tool_use_id=call.id, name=call.name,
                        content=json.dumps({
                            "blocked": True,
                            "reasons": [f.message for f in pre_findings],
                        }),
                    ))
                    yield StreamEvent(
                        type="tool_result",
                        payload={
                            "step": steps, "name": call.name, "status": "blocked",
                            "artifact_ids": [],
                            "preview": str([f.code for f in pre_findings]),
                        },
                    )
                    continue

                # Emit a2a_start before sub-agent delegation so the parent
                # client can show a nested progress indicator.
                if call.name == "delegate_subagent":
                    _a2a_calls.add(call.id)
                    task_preview = str(call.arguments.get("task", ""))[:200]
                    yield StreamEvent(
                        type="a2a_start",
                        payload={
                            "step": steps,
                            "task_preview": task_preview,
                            "tools_allowed": call.arguments.get("tools_allowed", []),
                        },
                    )

                self._hook_runner.run_pre(call.name, call.arguments, session_id=session_id)
                _scheduled.append(call)

            # ── Phase 2: Dispatch (parallel or sequential) ────────────────────
            _dispatch_times: dict[str, int] = {}
            _results: dict[str, ToolResult] = {}

            if _should_parallelize(_scheduled):
                def _timed_dispatch(c: ToolCall) -> tuple[ToolResult, int]:
                    t = time.monotonic()
                    return self._dispatcher.dispatch(c), int((time.monotonic() - t) * 1000)

                with ThreadPoolExecutor(max_workers=len(_scheduled)) as pool:
                    for call, (res, ms) in zip(
                        _scheduled, pool.map(_timed_dispatch, _scheduled)
                    ):
                        _results[call.id] = res
                        _dispatch_times[call.id] = ms
            else:
                for call in _scheduled:
                    _t = time.monotonic()
                    _results[call.id] = self._dispatcher.dispatch(call)
                    _dispatch_times[call.id] = int((time.monotonic() - _t) * 1000)

            # ── Phase 3: Post-hooks, trace, state updates, tool_result events ─
            for call in _scheduled:
                result: ToolResult = _results[call.id]
                _dispatch_ms = _dispatch_times[call.id]

                self._hook_runner.run_post(
                    call.name,
                    result.payload if isinstance(result.payload, dict) else {},
                    session_id=session_id,
                )

                # Tool call trace event
                try:
                    from app.trace.publishers import publish_tool_call as _pub_tc  # noqa: PLC0415
                    _tool_out = (result.payload if isinstance(result.payload, dict)
                                 else {"value": result.payload})
                    _pub_tc(
                        turn=steps,
                        tool_name=call.name,
                        tool_input=dict(call.arguments),
                        tool_output=str(_tool_out)[:4096],
                        duration_ms=_dispatch_ms,
                        error=None if result.ok else str(result.payload)[:512],
                    )
                except Exception:  # noqa: BLE001
                    pass

                report = post_tool(result)
                for aid in report.new_artifact_ids:
                    state.record_artifact(aid)

                # Keep scratchpad in sync when the agent writes working.md and
                # emit a live delta so the frontend panel can update in real time.
                if call.name == "write_working" and result.ok:
                    new_pad = (result.payload or {}).get("content", "")
                    if new_pad:
                        state.scratchpad = new_pad
                        yield StreamEvent(
                            type="scratchpad_delta",
                            payload={"content": new_pad},
                        )
                        try:
                            from app.trace.publishers import publish_scratchpad_write as _pub_sw  # noqa: PLC0415
                            _pub_sw(turn=steps, key="working.md", value_preview=new_pad[:200])
                        except Exception:  # noqa: BLE001
                            pass

                # Emit todos_update when todo_write succeeds so the frontend
                # task panel refreshes in real time (P19).
                if call.name == "todo_write" and result.ok:
                    new_todos = (result.payload or {}).get("todos", [])
                    yield StreamEvent(
                        type="todos_update",
                        payload={"todos": new_todos},
                    )

                state.record_tool(
                    name=call.name,
                    result_payload=(result.payload
                                    if isinstance(result.payload, dict) else
                                    {"value": result.payload}),
                    status="ok" if result.ok else "error",
                )
                content = json.dumps(_serializable(result.payload))
                if report.trimmed_stdout:
                    content = json.dumps({
                        "artifact_refs": list(report.new_artifact_ids),
                        "trimmed_preview": report.trimmed_stdout,
                    })
                messages.append(Message(
                    role="tool", tool_use_id=call.id, name=call.name, content=content,
                ))

                if call.id in _a2a_calls:
                    payload_dict = result.payload if isinstance(result.payload, dict) else {}
                    yield StreamEvent(
                        type="a2a_end",
                        payload={
                            "step": steps,
                            "artifact_id": payload_dict.get("artifact_id", ""),
                            "summary": payload_dict.get("summary", "")[:200],
                            "ok": result.ok,
                        },
                    )

                yield StreamEvent(
                    type="tool_result",
                    payload={
                        "step": steps,
                        "name": call.name,
                        "status": "ok" if result.ok else "error",
                        "artifact_ids": list(report.new_artifact_ids),
                        "preview": str(result.payload)[:200],
                    },
                )
        else:
            stop_reason = "max_steps"

        end_findings = end_of_turn(scratchpad=state.scratchpad, claims=[])
        outcomes.append(apply_tier(client.tier, end_findings))

        yield StreamEvent(
            type="turn_end",
            payload={
                "final_text": final_text,
                "stop_reason": stop_reason,
                "steps": steps,
            },
        )


def _serializable(value: object) -> object:
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _arg_preview(arguments: dict[str, object], max_len: int = 120) -> str:
    """Return a short human-readable preview of tool arguments."""
    text = json.dumps(arguments)
    return text[:max_len] + ("…" if len(text) > max_len else "")


_SYNTHESIS_SYSTEM = (
    "You are a helpful data analyst. The user asked a question and you already ran "
    "Python queries to gather data. Write a complete, clear markdown response that "
    "directly answers their question using the results provided. Do not call any tools."
)


def _build_synthesis_messages(
    user_message: str,
    messages: list[Message],
    keep_results: int = 3,
    result_chars: int = 800,
) -> list[Message]:
    """Build a minimal fresh message list for the synthesis step.

    Free models often return empty text when the full conversation history is
    very long (many tool call / result pairs).  This helper extracts the last
    ``keep_results`` tool-result payloads, inlines them as a compact summary,
    and wraps the original user question into a fresh two-message conversation.
    The model only sees a short context, so it can synthesise without hitting
    context-window or attention limits.
    """
    tool_msgs = [m for m in messages if m.role == "tool"]
    recent = tool_msgs[-keep_results:]
    snippets: list[str] = []
    for i, m in enumerate(recent, 1):
        content = (m.content or "")[:result_chars]
        snippets.append(f"Result {i}:\n{content}")
    summary = "\n\n".join(snippets) if snippets else "(no query results available)"
    synthesis_user = (
        f"You ran several data queries. Here are the most recent results:\n\n"
        f"{summary}\n\n"
        f"Now write a complete markdown response answering the user's original question:\n"
        f'"{user_message}"\n\n'
        f"Include the specific numbers you found, cite any artifact IDs you saved, "
        f"and include any charts, tables, or diagrams requested."
    )
    return [Message(role="user", content=synthesis_user)]
