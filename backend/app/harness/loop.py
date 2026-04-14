from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
)
from app.harness.dispatcher import ToolDispatcher, ToolResult
from app.harness.guardrails.end_of_turn import end_of_turn
from app.harness.guardrails.post_tool import post_tool
from app.harness.guardrails.pre_tool import pre_tool_gate
from app.harness.guardrails.tiers import apply_tier
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.turn_state import TurnState


@dataclass
class LoopOutcome:
    final_text: str
    steps: int
    stop_reason: str
    turn_state: TurnState
    guardrail_outcomes: list[GuardrailOutcome] = field(default_factory=list)


class AgentLoop:
    def __init__(self, dispatcher: ToolDispatcher) -> None:
        self._dispatcher = dispatcher

    def run(
        self,
        client: ModelClient,
        system: str,
        user_message: str,
        dataset_loaded: bool,
        max_steps: int = 12,
        scratchpad: str = "",
    ) -> LoopOutcome:
        state = TurnState(dataset_loaded=dataset_loaded, scratchpad=scratchpad)
        messages: list[Message] = [Message(role="user", content=user_message)]
        outcomes: list[GuardrailOutcome] = []
        final_text = ""
        steps = 0
        stop_reason = "end_turn"

        for steps in range(1, max_steps + 1):
            resp = client.complete(CompletionRequest(
                system=system, messages=tuple(messages),
                tools=(), max_tokens=2048,
            ))
            final_text = resp.text

            if not resp.tool_calls:
                stop_reason = resp.stop_reason or "end_turn"
                break

            messages.append(Message(role="assistant", content=resp.text or ""))
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

                result: ToolResult = self._dispatcher.dispatch(call)
                report = post_tool(result)
                for aid in report.new_artifact_ids:
                    state.record_artifact(aid)
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


def _serializable(value):
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
