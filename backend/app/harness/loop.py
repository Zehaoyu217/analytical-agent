from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field

from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
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
    ) -> LoopOutcome:
        state = TurnState(dataset_loaded=dataset_loaded, scratchpad=scratchpad)
        messages: list[Message] = [Message(role="user", content=user_message)]
        outcomes: list[GuardrailOutcome] = []
        final_text = ""
        steps = 0
        stop_reason = "end_turn"

        for step in range(1, max_steps + 1):
            steps = step
            messages, _ = self._compactor.maybe_compact(messages)
            resp = client.complete(CompletionRequest(
                system=system, messages=tuple(messages),
                tools=tools, max_tokens=2048,
            ))
            final_text = resp.text

            if not resp.tool_calls:
                stop_reason = resp.stop_reason or "end_turn"
                break

            messages.append(Message(
                role="assistant",
                content=resp.text or "",
                tool_calls=tuple(resp.tool_calls),
            ))
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
                result: ToolResult = self._dispatcher.dispatch(call)
                self._hook_runner.run_post(
                    call.name,
                    result.payload if isinstance(result.payload, dict) else {},
                )
                report = post_tool(result)
                for aid in report.new_artifact_ids:
                    state.record_artifact(aid)
                # Keep scratchpad in sync when the agent writes working.md.
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
                    content = json.dumps({"artifact_refs": list(report.new_artifact_ids),
                                          "trimmed_preview": report.trimmed_stdout})
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
    ) -> Generator[StreamEvent, None, None]:
        """Run the agent loop, yielding a StreamEvent for each notable moment.

        Yields turn_start before each LLM call, tool_call / tool_result around
        each dispatch, and turn_end when the loop exits.  Callers can serialise
        each event to SSE via ``event.to_sse()``.

        A ``scratchpad_delta`` event is emitted whenever the agent calls the
        ``write_working`` tool, carrying the full new scratchpad content so the
        UI can show live reasoning.
        """
        state = TurnState(dataset_loaded=dataset_loaded, scratchpad=scratchpad)
        messages: list[Message] = [Message(role="user", content=user_message)]
        outcomes: list[GuardrailOutcome] = []
        final_text = ""
        steps = 0
        stop_reason = "end_turn"

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

            resp = client.complete(CompletionRequest(
                system=system, messages=tuple(messages),
                tools=tools, max_tokens=2048,
            ))
            final_text = resp.text

            if not resp.tool_calls:
                stop_reason = resp.stop_reason or "end_turn"
                break

            messages.append(Message(
                role="assistant",
                content=resp.text or "",
                tool_calls=tuple(resp.tool_calls),
            ))
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
                is_a2a = call.name == "delegate_subagent"
                if is_a2a:
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
                result: ToolResult = self._dispatcher.dispatch(call)
                self._hook_runner.run_post(
                    call.name,
                    result.payload if isinstance(result.payload, dict) else {},
                    session_id=session_id,
                )
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

                if is_a2a:
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
