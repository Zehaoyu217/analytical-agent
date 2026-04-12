from __future__ import annotations

from pathlib import Path

import pytest

from app.trace import bus
from app.trace.events import (
    CompactionEvent,
    LlmCallEvent,
    PromptSection,
    ScratchpadWriteEvent,
    SessionStartEvent,
    ToolCallEvent,
)
from app.trace.publishers import (
    TraceSession,
    publish_compaction,
    publish_final_output,
    publish_llm_call,
    publish_scratchpad_write,
    publish_session_start,
    publish_tool_call,
)


@pytest.fixture(autouse=True)
def _reset_bus() -> None:
    bus.reset()


def test_publish_session_start() -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    publish_session_start(
        session_id="sess", started_at="t",
        level=3, level_label="eval-level3", input_query="q",
    )
    assert len(received) == 1
    assert isinstance(received[0], SessionStartEvent)


def test_publish_llm_call() -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    publish_llm_call(
        step_id="s1", turn=1, model="m", temperature=1.0,
        max_tokens=10, prompt_text="p",
        sections=[PromptSection(source="x", lines="1-10", text="...")],
        response_text="r", tool_calls=[], stop_reason="end_turn",
        input_tokens=100, output_tokens=20,
        cache_read_tokens=0, cache_creation_tokens=0, latency_ms=50,
    )
    assert isinstance(received[0], LlmCallEvent)
    assert received[0].step_id == "s1"


def test_publish_tool_call() -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    publish_tool_call(
        turn=1, tool_name="t", tool_input={"a": 1},
        tool_output="y", duration_ms=10, error=None,
    )
    assert isinstance(received[0], ToolCallEvent)


def test_publish_compaction() -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    publish_compaction(
        turn=1, before_token_count=1000, after_token_count=500,
        dropped_layers=["a"], kept_layers=["b"],
    )
    assert isinstance(received[0], CompactionEvent)


def test_publish_scratchpad_write() -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    publish_scratchpad_write(turn=1, key="k", value_preview="v")
    assert isinstance(received[0], ScratchpadWriteEvent)


def test_trace_session_context_publishes_start_and_end(tmp_path: Path) -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    with TraceSession(
        session_id="sess", level=3, level_label="eval-level3",
        input_query="q", trace_mode="always", output_dir=tmp_path,
    ) as session:
        publish_final_output(
            output_text="out", final_grade="A", judge_dimensions={"a": 1.0},
        )
        session.set_final_grade("A")
    kinds = [e.kind for e in received]
    assert kinds[0] == "session_start"
    assert "final_output" in kinds
    assert kinds[-1] == "session_end"


def test_trace_session_writes_trace_file_when_always(tmp_path: Path) -> None:
    with TraceSession(
        session_id="sess-w", level=3, level_label="eval-level3",
        input_query="q", trace_mode="always", output_dir=tmp_path,
    ) as session:
        publish_final_output(
            output_text="out", final_grade="F", judge_dimensions={},
        )
        session.set_final_grade("F")
    assert (tmp_path / "sess-w.yaml").exists()


def test_trace_session_skips_write_on_failure_mode_when_grade_passes(
    tmp_path: Path,
) -> None:
    with TraceSession(
        session_id="sess-s", level=3, level_label="eval-level3",
        input_query="q", trace_mode="on_failure", output_dir=tmp_path,
    ) as session:
        publish_final_output(
            output_text="out", final_grade="A", judge_dimensions={},
        )
        session.set_final_grade("A")
    assert not (tmp_path / "sess-s.yaml").exists()


def test_context_manager_record_compaction_emits_event(tmp_path: Path) -> None:
    from app.context.manager import ContextManager
    received: list[object] = []
    bus.subscribe(received.append)
    cm = ContextManager()
    cm.set_turn(3)
    cm.record_compaction(
        tokens_before=1000, tokens_after=400,
        removed=[{"name": "layer_a", "tokens": 300},
                 {"name": "layer_b", "tokens": 300}],
        survived=["layer_c"],
    )
    compactions = [e for e in received if isinstance(e, CompactionEvent)]
    assert len(compactions) == 1
    assert compactions[0].turn == 3
    assert compactions[0].before_token_count == 1000
    assert compactions[0].after_token_count == 400
    assert compactions[0].dropped_layers == ["layer_a", "layer_b"]
    assert compactions[0].kept_layers == ["layer_c"]
