from __future__ import annotations

import pytest

from app.trace.assembler import (
    StepNotFoundError,
    assemble_prompt,
    detect_conflicts,
)
from app.trace.events import (
    LlmCallEvent,
    PromptSection,
    SessionEndEvent,
    SessionStartEvent,
    Trace,
    TraceSummary,
)


def _trace(sections_per_step: dict[str, list[PromptSection]]) -> Trace:
    step_ids = list(sections_per_step.keys())
    events: list[object] = [
        SessionStartEvent(
            seq=1, timestamp="t", session_id="sess-1", started_at="t",
            level=3, level_label="eval-level3", input_query="q",
        ),
    ]
    for i, step_id in enumerate(step_ids, start=2):
        events.append(LlmCallEvent(
            seq=i, timestamp="t", step_id=step_id, turn=1,
            model="m", temperature=1.0, max_tokens=10, prompt_text="p",
            sections=sections_per_step[step_id], response_text="r",
            tool_calls=[], stop_reason="end_turn",
            input_tokens=0, output_tokens=0,
            cache_read_tokens=0, cache_creation_tokens=0, latency_ms=0,
        ))
    events.append(SessionEndEvent(
        seq=99, timestamp="t", ended_at="t",
        duration_ms=1, outcome="ok", error=None,
    ))
    return Trace(
        trace_schema_version=1,
        summary=TraceSummary(
            session_id="sess-1", started_at="t", ended_at="t",
            duration_ms=1, level=3, level_label="eval-level3",
            turn_count=1, llm_call_count=len(step_ids),
            total_input_tokens=0, total_output_tokens=0,
            outcome="ok", final_grade=None,
            step_ids=step_ids, trace_mode="always",
            judge_runs_cached=0,
        ),
        judge_runs=[],
        events=events,  # type: ignore[arg-type]
    )


def test_assemble_returns_sections_for_step() -> None:
    sections = [
        PromptSection(source="SYSTEM_PROMPT", lines="1-50", text="..."),
        PromptSection(source="user_query", lines="51-52", text="..."),
    ]
    trace = _trace({"s1": sections})
    result = assemble_prompt(trace, "s1")
    assert result["sections"] == [s.model_dump() for s in sections]
    assert result["conflicts"] == []


def test_assemble_raises_for_missing_step() -> None:
    trace = _trace({"s1": []})
    with pytest.raises(StepNotFoundError):
        assemble_prompt(trace, "s99")


def test_detect_conflicts_flags_overlapping_ranges() -> None:
    sections = [
        PromptSection(source="rules.md", lines="100-150", text="a"),
        PromptSection(source="rules.md", lines="120-170", text="b"),
    ]
    conflicts = detect_conflicts(sections)
    assert len(conflicts) == 1
    assert conflicts[0]["source_a"] == "rules.md"
    assert conflicts[0]["source_b"] == "rules.md"
    assert conflicts[0]["overlap"] == "120-150"


def test_detect_conflicts_ignores_different_sources() -> None:
    sections = [
        PromptSection(source="a.md", lines="1-10", text="a"),
        PromptSection(source="b.md", lines="1-10", text="b"),
    ]
    assert detect_conflicts(sections) == []


def test_detect_conflicts_ignores_non_overlapping_same_source() -> None:
    sections = [
        PromptSection(source="a.md", lines="1-10", text="a"),
        PromptSection(source="a.md", lines="20-30", text="b"),
    ]
    assert detect_conflicts(sections) == []


def test_detect_conflicts_handles_malformed_range() -> None:
    sections = [
        PromptSection(source="a.md", lines="garbage", text="a"),
        PromptSection(source="a.md", lines="1-10", text="b"),
    ]
    assert detect_conflicts(sections) == []
