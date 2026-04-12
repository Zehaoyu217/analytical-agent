from __future__ import annotations

import time
from pathlib import Path

import yaml

from app.trace.retention import delete_all, delete_by_age, delete_by_grade


def _write_trace(dir_: Path, session_id: str, grade: str | None) -> Path:
    path = dir_ / f"{session_id}.yaml"
    path.write_text(yaml.safe_dump({
        "trace_schema_version": 1,
        "summary": {
            "session_id": session_id, "started_at": "t", "ended_at": "t",
            "duration_ms": 1, "level": 3, "level_label": "x",
            "turn_count": 0, "llm_call_count": 0,
            "total_input_tokens": 0, "total_output_tokens": 0,
            "outcome": "ok", "final_grade": grade,
            "step_ids": [], "trace_mode": "always", "judge_runs_cached": 0,
        },
        "judge_runs": [],
        "events": [],
    }), encoding="utf-8")
    return path


def test_delete_all_removes_all_yaml_files(tmp_path: Path) -> None:
    _write_trace(tmp_path, "a", "F")
    _write_trace(tmp_path, "b", "A")
    (tmp_path / "notes.txt").write_text("keep")
    count = delete_all(tmp_path)
    assert count == 2
    assert not (tmp_path / "a.yaml").exists()
    assert (tmp_path / "notes.txt").exists()


def test_delete_by_grade_keeps_matching_grades(tmp_path: Path) -> None:
    _write_trace(tmp_path, "fail1", "F")
    _write_trace(tmp_path, "pass1", "A")
    _write_trace(tmp_path, "pass2", "B")
    count = delete_by_grade(tmp_path, keep_grades={"A", "B"})
    assert count == 1
    assert not (tmp_path / "fail1.yaml").exists()
    assert (tmp_path / "pass1.yaml").exists()
    assert (tmp_path / "pass2.yaml").exists()


def test_delete_by_age_removes_old_files(tmp_path: Path) -> None:
    old = _write_trace(tmp_path, "old", "F")
    fresh = _write_trace(tmp_path, "fresh", "F")
    old_time = time.time() - 60 * 60 * 24 * 60  # 60 days ago
    import os
    os.utime(old, (old_time, old_time))
    count = delete_by_age(tmp_path, older_than_days=30)
    assert count == 1
    assert not old.exists()
    assert fresh.exists()


def test_delete_all_empty_dir_returns_zero(tmp_path: Path) -> None:
    assert delete_all(tmp_path) == 0
