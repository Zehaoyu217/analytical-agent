"""Typed publish helpers + TraceSession context manager.

Agent code uses these instead of constructing event objects directly.
The bus assigns seq at publish time; callers pass seq=0 as a placeholder.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from app.trace import bus
from app.trace.events import (
    CompactionEvent,
    FinalOutputEvent,
    Grade,
    LlmCallEvent,
    PromptSection,
    ScratchpadWriteEvent,
    SessionEndEvent,
    SessionStartEvent,
    ToolCallEvent,
)
from app.trace.recorder import JudgeRunner, TraceRecorder


def _now() -> str:
    return datetime.now(UTC).isoformat()


def publish_session_start(
    session_id: str, started_at: str, level: int,
    level_label: str, input_query: str,
) -> None:
    bus.publish(SessionStartEvent(
        seq=0, timestamp=_now(),
        session_id=session_id, started_at=started_at,
        level=level, level_label=level_label, input_query=input_query,
    ))


def publish_llm_call(
    step_id: str, turn: int, model: str, temperature: float,
    max_tokens: int, prompt_text: str, sections: list[PromptSection],
    response_text: str, tool_calls: list[dict[str, object]],
    stop_reason: str, input_tokens: int, output_tokens: int,
    cache_read_tokens: int, cache_creation_tokens: int, latency_ms: int,
) -> None:
    bus.publish(LlmCallEvent(
        seq=0, timestamp=_now(), step_id=step_id, turn=turn,
        model=model, temperature=temperature, max_tokens=max_tokens,
        prompt_text=prompt_text, sections=sections,
        response_text=response_text, tool_calls=tool_calls,
        stop_reason=stop_reason, input_tokens=input_tokens,
        output_tokens=output_tokens, cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens, latency_ms=latency_ms,
    ))


def publish_tool_call(
    turn: int, tool_name: str, tool_input: dict[str, object],
    tool_output: str, duration_ms: int, error: str | None,
) -> None:
    bus.publish(ToolCallEvent(
        seq=0, timestamp=_now(), turn=turn, tool_name=tool_name,
        tool_input=tool_input, tool_output=tool_output,
        duration_ms=duration_ms, error=error,
    ))


def publish_compaction(
    turn: int, before_token_count: int, after_token_count: int,
    dropped_layers: list[str], kept_layers: list[str],
) -> None:
    bus.publish(CompactionEvent(
        seq=0, timestamp=_now(), turn=turn,
        before_token_count=before_token_count,
        after_token_count=after_token_count,
        dropped_layers=dropped_layers, kept_layers=kept_layers,
    ))


def publish_scratchpad_write(turn: int, key: str, value_preview: str) -> None:
    bus.publish(ScratchpadWriteEvent(
        seq=0, timestamp=_now(), turn=turn,
        key=key, value_preview=value_preview,
    ))


def publish_final_output(
    output_text: str, final_grade: Grade | None,
    judge_dimensions: dict[str, float],
) -> None:
    bus.publish(FinalOutputEvent(
        seq=0, timestamp=_now(), output_text=output_text,
        final_grade=final_grade, judge_dimensions=judge_dimensions,
    ))


def publish_session_end(
    ended_at: str, duration_ms: int,
    outcome: str, error: str | None,
) -> None:
    bus.publish(SessionEndEvent(
        seq=0, timestamp=_now(), ended_at=ended_at,
        duration_ms=duration_ms,
        outcome=outcome,  # type: ignore[arg-type]
        error=error,
    ))


class TraceSession:
    """Context manager that wires a recorder to the bus and finalizes on exit."""

    def __init__(
        self,
        session_id: str,
        level: int,
        level_label: str,
        input_query: str,
        trace_mode: str,
        output_dir: Path,
        judge_runner: JudgeRunner | None = None,
    ) -> None:
        self._session_id = session_id
        self._level = level
        self._level_label = level_label
        self._input_query = input_query
        self._trace_mode = trace_mode
        self._output_dir = output_dir
        self._judge_runner = judge_runner
        self._final_grade: Grade | None = None
        self._started_at: str = ""
        self._recorder: TraceRecorder | None = None

    def set_final_grade(self, grade: Grade | None) -> None:
        self._final_grade = grade

    def __enter__(self) -> TraceSession:
        self._recorder = TraceRecorder(
            session_id=self._session_id,
            trace_mode=self._trace_mode,
            output_dir=self._output_dir,
            judge_runner=self._judge_runner,
        )
        bus.subscribe(self._recorder.on_event)
        self._started_at = _now()
        publish_session_start(
            session_id=self._session_id,
            started_at=self._started_at,
            level=self._level,
            level_label=self._level_label,
            input_query=self._input_query,
        )
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, tb: TracebackType | None,
    ) -> None:
        outcome = "ok" if exc is None else "error"
        error = None if exc is None else str(exc)
        ended_at = _now()
        publish_session_end(
            ended_at=ended_at, duration_ms=0, outcome=outcome, error=error,
        )
        if self._recorder is not None:
            bus.unsubscribe(self._recorder.on_event)
            self._recorder.finalize(self._final_grade)
