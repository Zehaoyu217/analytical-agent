from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.trace.store import TraceNotFoundError, list_traces, load_trace


def _minimal_trace_yaml(session_id: str, grade: str | None = "F") -> dict[str, object]:
    return {
        "trace_schema_version": 1,
        "summary": {
            "session_id": session_id, "started_at": "t1", "ended_at": "t2",
            "duration_ms": 1000, "level": 3, "level_label": "eval-level3",
            "turn_count": 1, "llm_call_count": 1,
            "total_input_tokens": 100, "total_output_tokens": 20,
            "outcome": "ok", "final_grade": grade,
            "step_ids": ["s1"], "trace_mode": "on_failure",
            "judge_runs_cached": 0,
        },
        "judge_runs": [],
        "events": [
            {
                "kind": "session_start", "seq": 1, "timestamp": "t1",
                "session_id": session_id, "started_at": "t1",
                "level": 3, "level_label": "eval-level3", "input_query": "q",
            },
            {
                "kind": "session_end", "seq": 2, "timestamp": "t2",
                "ended_at": "t2", "duration_ms": 1000,
                "outcome": "ok", "error": None,
            },
        ],
    }


def _write(dir_: Path, session_id: str, grade: str | None = "F") -> None:
    (dir_ / f"{session_id}.yaml").write_text(
        yaml.safe_dump(_minimal_trace_yaml(session_id, grade)),
        encoding="utf-8",
    )


def test_list_traces_returns_summaries_sorted_by_session_id(tmp_path: Path) -> None:
    _write(tmp_path, "sess-b")
    _write(tmp_path, "sess-a")
    _write(tmp_path, "sess-c")
    summaries = list_traces(tmp_path)
    assert [s.session_id for s in summaries] == ["sess-a", "sess-b", "sess-c"]


def test_list_traces_returns_empty_list_when_dir_missing(tmp_path: Path) -> None:
    assert list_traces(tmp_path / "missing") == []


def test_list_traces_skips_non_yaml_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hi")
    _write(tmp_path, "sess-1")
    summaries = list_traces(tmp_path)
    assert [s.session_id for s in summaries] == ["sess-1"]


def test_load_trace_returns_full_trace(tmp_path: Path) -> None:
    _write(tmp_path, "sess-1")
    trace = load_trace(tmp_path, "sess-1")
    assert trace.summary.session_id == "sess-1"
    assert len(trace.events) == 2


def test_load_trace_raises_on_invalid_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid trace_id"):
        load_trace(tmp_path, "../etc/passwd")


def test_load_trace_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(TraceNotFoundError):
        load_trace(tmp_path, "missing")


def test_load_trace_raises_on_corrupted_yaml(tmp_path: Path) -> None:
    (tmp_path / "sess-1.yaml").write_text(": : :", encoding="utf-8")
    with pytest.raises(ValueError):
        load_trace(tmp_path, "sess-1")


def test_list_traces_skips_corrupted_files(tmp_path: Path) -> None:
    _write(tmp_path, "good")
    (tmp_path / "bad.yaml").write_text("not valid: : :", encoding="utf-8")
    summaries = list_traces(tmp_path)
    assert [s.session_id for s in summaries] == ["good"]
