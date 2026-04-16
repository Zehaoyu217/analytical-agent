from __future__ import annotations

import json
import re
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
    ToolCall,
    ToolSchema,
)
from app.harness.compactor import MicroCompactor
from app.harness.dispatcher import ToolDispatcher, ToolResult
from app.harness.guardrails.end_of_turn import end_of_turn
from app.harness.guardrails.post_tool import post_tool
from app.harness.guardrails.pre_tool import pre_tool_gate
from app.harness.guardrails.tiers import apply_tier
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.hooks import HookRunner
from app.harness.semantic_compactor import SemanticCompactionResult, SemanticCompactor
from app.harness.stream_events import StreamEvent
from app.harness.turn_state import TurnState


# ── Parallel-safe tool dispatch (Hermes H3b) ─────────────────────────────────
#
# A small whitelist of tools whose handlers are read-only and have no shared
# mutable state, so calling them concurrently in a thread pool is safe. The
# read-only contract means the order in which they execute does not affect the
# final result, only the order of side-effect-free mutations to ``state._log``.
PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset({
    "skill",
    "read_file",
    "glob_files",
    "search_text",
    "session_search",
    "get_artifact",
    "get_context_status",
})

# Hard-deny set: any tool that mutates wiki, scratchpad, artifacts, sandbox
# bootstrap globals, or recurses into another agent.
NEVER_PARALLEL_TOOLS: frozenset[str] = frozenset({
    "write_working",
    "todo_write",
    "promote_finding",
    "save_artifact",
    "update_artifact",
    "delegate_subagent",
    "execute_python",
    "sandbox.run",
})

_PARALLEL_MAX_WORKERS = 8


def _should_parallelize(calls: tuple[ToolCall, ...] | list[ToolCall]) -> bool:
    """Return True only when every call in *calls* is in the safe whitelist.

    Conservative: requires len ≥ 2, no never-parallel tool, all calls in the
    explicit safe set (unknown tools fall back to sequential).
    """
    if len(calls) < 2:
        return False
    if any(c.name in NEVER_PARALLEL_TOOLS for c in calls):
        return False
    return all(c.name in PARALLEL_SAFE_TOOLS for c in calls)


@dataclass
class _SingleToolResult:
    """Per-call result from ``_dispatch_single_call``.

    ``run()`` uses only ``status`` and ``tool_message``.
    ``run_stream()`` uses every field to emit the appropriate ``StreamEvent``s
    without re-inspecting state after the fact.
    """

    call: ToolCall
    status: str                   # "ok" | "error" | "blocked"
    pre_outcome: GuardrailOutcome
    tool_message: Message         # ready to append to the conversation
    artifact_ids: frozenset[str]
    scratchpad_update: str | None  # non-None when write_working succeeded
    todo_update: list | None       # non-None when todo_write succeeded
    is_a2a: bool
    a2a_task_preview: str
    a2a_tools_allowed: list
    a2a_artifact_id: str
    a2a_summary: str
    a2a_ok: bool
    result_payload: object         # raw payload for preview / trace
    dispatch_ms: int


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
        semantic_compactor: SemanticCompactor | None = None,
        context_token_budget: int = 200_000,
    ) -> None:
        self._dispatcher = dispatcher
        self._compactor = compactor or MicroCompactor()
        self._hook_runner = hook_runner or HookRunner()
        self._semantic_compactor = semantic_compactor
        self._context_token_budget = context_token_budget

    # ── v4 P24: post-turn inline-table fix-up ────────────────────────────────

    def _maybe_inject_inline_table(
        self,
        client: ModelClient,
        user_message: str,
        messages: list[Message],
        final_text: str,
        stop_reason: str,
    ) -> tuple[str, bool]:
        """Re-synthesise *final_text* with a markdown table when the user asked.

        Returns ``(final_text, injected)`` where *injected* is True iff the
        re-synthesis call ran AND produced new non-empty text containing a
        table. Otherwise the original *final_text* is returned untouched.
        """
        if stop_reason not in ("end_turn", "max_steps"):
            return final_text, False
        if not _user_wants_inline_table(user_message):
            return final_text, False
        if _response_has_table(final_text):
            return final_text, False

        synth_msgs = _build_inline_table_messages(user_message, messages, final_text)
        try:
            resp = client.complete(CompletionRequest(
                system=_INLINE_TABLE_SYSTEM,
                messages=tuple(synth_msgs),
                tools=(), tool_choice=None, max_tokens=4096,
            ))
        except Exception:  # noqa: BLE001 — never crash the turn over a fix-up
            return final_text, False

        new_text = (resp.text or "").strip()
        # Only adopt the rewrite if it actually contains a table now.
        if new_text and _response_has_table(new_text):
            return new_text, True
        return final_text, False

    # ── stage-2 semantic compaction ───────────────────────────────────────────

    def _maybe_semantic_compact(
        self,
        messages: list[Message],
        client: ModelClient,
    ) -> tuple[list[Message], SemanticCompactionResult | None]:
        """Run stage-2 semantic compaction when wired and over budget.

        Returns the (possibly-rewritten) message list and the report (or None
        when the compactor is not configured / threshold not crossed).
        """
        if self._semantic_compactor is None:
            return messages, None
        token_count = sum(len(m.content or "") for m in messages) // 4
        if not self._semantic_compactor.should_compact(
            messages, token_count, self._context_token_budget,
        ):
            return messages, None
        result = self._semantic_compactor.compact(messages, client)
        return result.messages, result

    # ── streaming event emission ──────────────────────────────────────────────

    def _emit_post_dispatch_events(
        self,
        tr: _SingleToolResult,
        steps: int,
    ) -> Generator[StreamEvent, None, None]:
        """Yield the SSE events that always follow a single tool dispatch.

        Centralised so both the serial and parallel branches of run_stream
        emit events in the same order with the same payload shape.
        """
        call = tr.call
        if tr.status == "blocked":
            yield StreamEvent(
                type="tool_result",
                payload={
                    "step": steps, "name": call.name, "status": "blocked",
                    "artifact_ids": [], "preview": str(tr.result_payload)[:200],
                },
            )
            return

        try:
            from app.trace.publishers import publish_tool_call as _pub_tc
            _pub_tc(
                turn=steps, tool_name=call.name,
                tool_input=dict(call.arguments),
                tool_output=str(tr.result_payload)[:4096],
                duration_ms=tr.dispatch_ms,
                error=None if tr.status == "ok" else str(tr.result_payload)[:512],
            )
        except Exception:  # noqa: BLE001
            pass

        if tr.scratchpad_update:
            yield StreamEvent(
                type="scratchpad_delta",
                payload={"content": tr.scratchpad_update},
            )
            try:
                from app.trace.publishers import publish_scratchpad_write as _pub_sw
                _pub_sw(turn=steps, key="working.md",
                        value_preview=tr.scratchpad_update[:200])
            except Exception:  # noqa: BLE001
                pass

        if tr.todo_update is not None:
            yield StreamEvent(
                type="todos_update",
                payload={"todos": tr.todo_update},
            )

        if tr.is_a2a:
            yield StreamEvent(
                type="a2a_end",
                payload={
                    "step": steps,
                    "artifact_id": tr.a2a_artifact_id,
                    "summary": tr.a2a_summary,
                    "ok": tr.a2a_ok,
                },
            )

        yield StreamEvent(
            type="tool_result",
            payload={
                "step": steps, "name": call.name,
                "status": tr.status,
                "artifact_ids": list(tr.artifact_ids),
                "preview": str(tr.result_payload)[:200],
            },
        )

    # ── shared tool dispatch ──────────────────────────────────────────────────

    def _dispatch_calls(
        self,
        calls: tuple[ToolCall, ...] | list[ToolCall],
        state: TurnState,
        outcomes: list[GuardrailOutcome],
        client: ModelClient,
        session_id: str = "",
    ) -> list[_SingleToolResult]:
        """Dispatch a batch of tool calls, in parallel when safe (Hermes H3b).

        Returns results in submission order regardless of completion order so
        downstream message append + SSE emission stay deterministic.
        """
        if not _should_parallelize(calls):
            return [
                self._dispatch_single_call(c, state, outcomes, client, session_id)
                for c in calls
            ]
        workers = min(_PARALLEL_MAX_WORKERS, len(calls))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(
                lambda c: self._dispatch_single_call(
                    c, state, outcomes, client, session_id,
                ),
                calls,
            ))

    def _dispatch_single_call(
        self,
        call: ToolCall,
        state: TurnState,
        outcomes: list[GuardrailOutcome],
        client: ModelClient,
        session_id: str = "",
    ) -> _SingleToolResult:
        """Dispatch one tool call: run guardrails, invoke handler, update state.

        Mutates *state* (scratchpad, artifact list, tool log) and *outcomes*
        in place.  Returns a ``_SingleToolResult`` with everything the streaming
        path needs to emit ``StreamEvent``s — the sync ``run()`` ignores most
        fields beyond ``status`` and ``tool_message``.
        """
        pre_findings = pre_tool_gate(
            call, turn_trace=state.as_trace(), dataset_loaded=state.dataset_loaded,
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
            blocked_msg = Message(
                role="tool", tool_use_id=call.id, name=call.name,
                content=json.dumps({
                    "blocked": True,
                    "reasons": [f.message for f in pre_findings],
                }),
            )
            return _SingleToolResult(
                call=call, status="blocked", pre_outcome=pre_outcome,
                tool_message=blocked_msg, artifact_ids=frozenset(),
                scratchpad_update=None, todo_update=None,
                is_a2a=False, a2a_task_preview="", a2a_tools_allowed=[],
                a2a_artifact_id="", a2a_summary="", a2a_ok=False,
                result_payload={"blocked": True, "findings": [f.code for f in pre_findings]},
                dispatch_ms=0,
            )

        is_a2a = call.name == "delegate_subagent"
        self._hook_runner.run_pre(call.name, call.arguments, session_id=session_id)
        _t0 = time.monotonic()
        result: ToolResult = self._dispatcher.dispatch(call)
        dispatch_ms = int((time.monotonic() - _t0) * 1000)
        self._hook_runner.run_post(
            call.name,
            result.payload if isinstance(result.payload, dict) else {},
            session_id=session_id,
        )
        report = post_tool(result)
        for aid in report.new_artifact_ids:
            state.record_artifact(aid)

        scratchpad_update: str | None = None
        if call.name == "write_working" and result.ok:
            new_pad = (result.payload or {}).get("content", "")
            if new_pad:
                state.scratchpad = new_pad
                scratchpad_update = new_pad

        todo_update: list | None = None
        if call.name == "todo_write" and result.ok:
            todo_update = (result.payload or {}).get("todos", [])

        state.record_tool(
            name=call.name,
            result_payload=(result.payload if isinstance(result.payload, dict)
                            else {"value": result.payload}),
            status="ok" if result.ok else "error",
        )
        if not result.ok:
            # Include the error message so the model understands what went wrong
            # and can recover (e.g., correct arguments, try a different approach).
            content = json.dumps({"error": result.error_message or "tool call failed"})
        else:
            content = json.dumps(_serializable(result.payload))
            if report.trimmed_stdout:
                content = json.dumps({
                    "artifact_refs": list(report.new_artifact_ids),
                    "trimmed_preview": report.trimmed_stdout,
                })
        tool_msg = Message(role="tool", tool_use_id=call.id, name=call.name, content=content)

        payload_dict = result.payload if isinstance(result.payload, dict) else {}
        # When a tool fails, surface the error string as result_payload so it
        # appears in SSE previews and the turn-state trace (easier debugging).
        effective_payload = (
            result.payload if result.ok
            else {"error": result.error_message or "tool call failed"}
        )
        return _SingleToolResult(
            call=call,
            status="ok" if result.ok else "error",
            pre_outcome=pre_outcome,
            tool_message=tool_msg,
            artifact_ids=frozenset(report.new_artifact_ids),
            scratchpad_update=scratchpad_update,
            todo_update=todo_update,
            is_a2a=is_a2a,
            a2a_task_preview=str(call.arguments.get("task", ""))[:200],
            a2a_tools_allowed=call.arguments.get("tools_allowed", []),
            a2a_artifact_id=payload_dict.get("artifact_id", ""),
            a2a_summary=payload_dict.get("summary", "")[:200],
            a2a_ok=result.ok,
            result_payload=effective_payload,
            dispatch_ms=dispatch_ms,
        )

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
        _synthesis_injected = False  # True after we inject a synthesis prompt

        for step in range(1, max_steps + 1):
            steps = step
            messages, _ = self._compactor.maybe_compact(messages)
            messages, _ = self._maybe_semantic_compact(messages, client)
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
            results = self._dispatch_calls(resp.tool_calls, state, outcomes, client)
            for tr in results:
                messages.append(tr.tool_message)
                # BLOCK: tool_message already contains the rejection payload; skip rest.
                if tr.status == "blocked":
                    continue
        else:
            stop_reason = "max_steps"

        # P24 — re-synthesise with an inline markdown table when the user
        # explicitly asked to "show / display / list" rows but the model
        # returned only an artifact citation.
        final_text, _ = self._maybe_inject_inline_table(
            client, user_message, messages, final_text, stop_reason,
        )

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

            messages, semantic_report = self._maybe_semantic_compact(messages, client)
            if semantic_report is not None and semantic_report.turns_summarized > 0:
                yield StreamEvent(
                    type="semantic_compact",
                    payload={
                        "step": steps,
                        "turns_summarized": semantic_report.turns_summarized,
                        "tokens_before": semantic_report.tokens_before,
                        "tokens_after": semantic_report.tokens_after,
                        "summary_preview": semantic_report.summary_preview,
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

            parallel = _should_parallelize(resp.tool_calls)
            if parallel:
                # Emit all tool_call previews first so the UI can render the
                # whole batch as "running" before any result arrives. Then run
                # dispatches concurrently and stream results in submission order.
                for call in resp.tool_calls:
                    yield StreamEvent(
                        type="tool_call",
                        payload={
                            "step": steps,
                            "name": call.name,
                            "input_preview": _arg_preview(call.arguments),
                        },
                    )
                results = self._dispatch_calls(
                    resp.tool_calls, state, outcomes, client, session_id,
                )
                for tr in results:
                    messages.append(tr.tool_message)
                    yield from self._emit_post_dispatch_events(tr, steps)
            else:
                for call in resp.tool_calls:
                    yield StreamEvent(
                        type="tool_call",
                        payload={
                            "step": steps,
                            "name": call.name,
                            "input_preview": _arg_preview(call.arguments),
                        },
                    )

                    # Emit a2a_start before dispatch so the parent client can show
                    # a nested progress indicator before the sub-agent runs.
                    is_a2a = call.name == "delegate_subagent"
                    if is_a2a:
                        yield StreamEvent(
                            type="a2a_start",
                            payload={
                                "step": steps,
                                "task_preview": str(call.arguments.get("task", ""))[:200],
                                "tools_allowed": call.arguments.get("tools_allowed", []),
                            },
                        )

                    tr = self._dispatch_single_call(call, state, outcomes, client, session_id)
                    messages.append(tr.tool_message)
                    yield from self._emit_post_dispatch_events(tr, steps)
        else:
            stop_reason = "max_steps"
            # Agent exhausted the step budget without writing a final response.
            # Force one synthesis call so the user always gets text back.
            if not final_text.strip() and messages:
                yield StreamEvent(type="turn_start", payload={"session_id": session_id, "step": steps + 1})
                try:
                    synth_msgs = _build_synthesis_messages(user_message, messages)
                    synth_req = CompletionRequest(
                        system=_SYNTHESIS_SYSTEM,
                        messages=tuple(synth_msgs),
                        tools=(),
                        tool_choice=None,
                    )
                    synth_resp = client.complete(synth_req)
                    final_text = (synth_resp.text or "").strip()
                except Exception:  # noqa: BLE001
                    pass

        # P24 — re-synthesise with an inline markdown table when the user
        # explicitly asked to "show / display / list" rows but the model
        # returned only an artifact citation.
        new_text, injected = self._maybe_inject_inline_table(
            client, user_message, messages, final_text, stop_reason,
        )
        if injected:
            final_text = new_text
            yield StreamEvent(
                type="inline_table",
                payload={
                    "step": steps,
                    "reason": "user_requested_table_not_in_response",
                },
            )

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


# ── v4 P24: inline-table synthesis ───────────────────────────────────────────

# Matches "show/display/list/give me … (table | top N | rows)" within ~60 chars.
_SHOW_TABLE_PATTERNS = re.compile(
    r"\b(show|display|list|give me)\b.{0,60}\b(table|top\s*\d+|rows?)\b",
    re.IGNORECASE | re.DOTALL,
)

# A markdown table row needs at least two pipes around two cells: `| a | b |`.
_TABLE_LINE_PATTERN = re.compile(r"^\|.+\|.+\|", re.MULTILINE)


def _user_wants_inline_table(user_message: str) -> bool:
    """True when the user explicitly asked for a table / top-N / rows."""
    return bool(_SHOW_TABLE_PATTERNS.search(user_message or ""))


def _response_has_table(text: str) -> bool:
    """True when *text* already contains at least one markdown table line."""
    return bool(_TABLE_LINE_PATTERN.search(text or ""))


_INLINE_TABLE_SYSTEM = """\
You are a data analyst rewriting a previously-drafted response.
The user explicitly asked to see rows displayed inline as a markdown table,
but the previous response only cited an artifact instead of showing the data.

Rewrite the response to include the requested rows as a markdown table
(up to 20 rows). Use the data already present in the most recent tool
results in the conversation. Keep the original headline, executive summary,
and caveats; just add the markdown table inside the Evidence section.

Do not call any tools. Output the full rewritten markdown response only.
"""


def _build_inline_table_messages(
    user_message: str,
    messages: list[Message],
    final_text: str,
    keep_results: int = 3,
    result_chars: int = 1500,
) -> list[Message]:
    """Build the synthesis prompt for the inline-table fix-up call.

    Surfaces the most recent tool-result payloads (which contain the printed
    DataFrame rows) so the model has the raw data without needing to call
    tools again.
    """
    tool_msgs = [m for m in messages if m.role == "tool"]
    recent = tool_msgs[-keep_results:]
    snippets: list[str] = []
    for i, m in enumerate(recent, 1):
        content = (m.content or "")[:result_chars]
        snippets.append(f"Tool result {i}:\n{content}")
    data_section = "\n\n".join(snippets) if snippets else "(no tool results available)"
    instruction = (
        f'The user asked: "{user_message}"\n\n'
        f"Recent tool results (use these for the table data):\n\n"
        f"{data_section}\n\n"
        f"Your previous response was:\n\n"
        f"{final_text}\n\n"
        f"Rewrite it to include a markdown table (≤20 rows) with the requested "
        f"rows inside the Evidence section. Keep the rest of the structure."
    )
    return [Message(role="user", content=instruction)]


_SYNTHESIS_SYSTEM = """\
You are a data analyst delivering findings to a non-technical executive audience.
The user asked a question and you already ran Python queries to gather the data.
Write a complete markdown response using exactly this three-section format — no exceptions:

## [Headline — one declarative sentence, plain English, numbers if impactful]

[Executive Summary — 2–4 sentences. What was asked. What the data shows. What it means for the decision. No jargon. No method description.]

---

### Evidence

- **[Artifact Title]** — one sentence: what this shows and why it matters

---

### Assumptions & Caveats

- [Specific data limitation, scope boundary, or statistical caveat. Always include at least one.]

Do not call any tools. Cite artifact titles you saved.
IMPORTANT: If the user explicitly asked to "show", "display", or "list" a specific table or set of rows, include those rows as a markdown table inline in this response (up to 20 rows) AND cite the artifact title. For all other data, cite by artifact title only — do not reproduce raw data inline.\
"""


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
