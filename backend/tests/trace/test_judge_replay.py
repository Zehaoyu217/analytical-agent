from __future__ import annotations

import pytest

from app.trace.events import (
    FinalOutputEvent,
    JudgeRun,
    SessionEndEvent,
    SessionStartEvent,
    Trace,
    TraceSummary,
)
from app.trace.judge_replay import (
    MissingApiKeyError,
    compute_variance,
    run_judge_variance,
)


def _trace(judge_runs: list[JudgeRun], output_text: str = "final") -> Trace:
    return Trace(
        trace_schema_version=1,
        summary=TraceSummary(
            session_id="sess", started_at="t", ended_at="t",
            duration_ms=1, level=3, level_label="eval-level3",
            turn_count=0, llm_call_count=0, total_input_tokens=0,
            total_output_tokens=0, outcome="ok", final_grade="F",
            step_ids=[], trace_mode="always",
            judge_runs_cached=len(judge_runs),
        ),
        judge_runs=judge_runs,
        events=[
            SessionStartEvent(
                seq=1, timestamp="t", session_id="sess", started_at="t",
                level=3, level_label="eval-level3", input_query="q",
            ),
            FinalOutputEvent(
                seq=2, timestamp="t", output_text=output_text,
                final_grade="F", judge_dimensions={},
            ),
            SessionEndEvent(
                seq=3, timestamp="t", ended_at="t",
                duration_ms=1, outcome="ok", error=None,
            ),
        ],
    )


def test_compute_variance_on_identical_runs_is_zero() -> None:
    runs = [JudgeRun(dimensions={"a": 1.0}) for _ in range(3)]
    variance = compute_variance(runs)
    assert variance == {"a": 0.0}


def test_compute_variance_spread() -> None:
    runs = [
        JudgeRun(dimensions={"a": 0.0}),
        JudgeRun(dimensions={"a": 1.0}),
    ]
    variance = compute_variance(runs)
    assert 0.4 < variance["a"] < 0.6  # spread is |max-min|/2 or std-dev-ish


def test_cached_path_returns_cached_variance() -> None:
    trace = _trace([
        JudgeRun(dimensions={"accuracy": 0.5}),
        JudgeRun(dimensions={"accuracy": 0.9}),
    ])
    result = run_judge_variance(trace, n=5, refresh=False, threshold=0.1)
    assert result["source"] == "cached"
    assert result["n"] == 2
    assert "accuracy" in result["variance"]
    assert result["threshold_exceeded"] == ["accuracy"]


def test_threshold_exceeded_is_empty_when_below_threshold() -> None:
    trace = _trace([
        JudgeRun(dimensions={"accuracy": 0.5}),
        JudgeRun(dimensions={"accuracy": 0.51}),
    ])
    result = run_judge_variance(trace, n=5, refresh=False, threshold=0.1)
    assert result["threshold_exceeded"] == []


def test_live_path_calls_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    trace = _trace([], output_text="the output")
    calls: list[tuple[str, int]] = []

    def runner(text: str, n: int) -> list[JudgeRun]:
        calls.append((text, n))
        return [JudgeRun(dimensions={"accuracy": float(i)}) for i in range(n)]

    result = run_judge_variance(
        trace, n=3, refresh=True, threshold=0.1,
        live_runner=runner, api_key="key",
    )
    assert calls == [("the output", 3)]
    assert result["source"] == "live"
    assert result["n"] == 3


def test_live_path_raises_when_api_key_missing() -> None:
    trace = _trace([])
    with pytest.raises(MissingApiKeyError):
        run_judge_variance(
            trace, n=3, refresh=True, threshold=0.1,
            live_runner=lambda _t, _n: [],
            api_key=None,
        )


def test_cached_path_returns_empty_when_no_runs() -> None:
    trace = _trace([])
    result = run_judge_variance(trace, n=5, refresh=False, threshold=0.1)
    assert result["variance"] == {}
    assert result["threshold_exceeded"] == []
    assert result["n"] == 0
