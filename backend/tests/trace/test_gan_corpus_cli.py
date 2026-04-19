"""Tests for the GAN trace-corpus CLI bridge."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "gan-trace-corpus.py"


def _load_module():  # noqa: ANN202
    spec = importlib.util.spec_from_file_location("gan_trace_corpus_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _trace_payload(session_id: str, started_at: str = "t1") -> dict[str, object]:
    return {
        "trace_schema_version": 1,
        "summary": {
            "session_id": session_id,
            "started_at": started_at,
            "ended_at": f"{started_at}-end",
            "duration_ms": 1000,
            "level": 3,
            "level_label": "eval-level3",
            "turn_count": 2,
            "llm_call_count": 3,
            "total_input_tokens": 100,
            "total_output_tokens": 20,
            "outcome": "ok",
            "final_grade": "A",
            "step_ids": ["s1"],
            "trace_mode": "on_failure",
            "judge_runs_cached": 0,
        },
        "judge_runs": [],
        "events": [
            {
                "kind": "session_start",
                "seq": 1,
                "timestamp": started_at,
                "session_id": session_id,
                "started_at": started_at,
                "level": 3,
                "level_label": "eval-level3",
                "input_query": "q",
            },
            {
                "kind": "session_end",
                "seq": 2,
                "timestamp": f"{started_at}-end",
                "ended_at": f"{started_at}-end",
                "duration_ms": 1000,
                "outcome": "ok",
                "error": None,
            },
        ],
    }


def _write_trace(dir_: Path, session_id: str, started_at: str = "t1") -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{session_id}.yaml").write_text(
        yaml.safe_dump(_trace_payload(session_id, started_at)),
        encoding="utf-8",
    )


def _run_main(mod, argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = mod.main(argv)
    captured = capsys.readouterr()
    return code, captured.out


def test_list_flag_prints_json_summaries(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:  # noqa: E501
    mod = _load_module()
    _write_trace(tmp_path, "sess-b", started_at="t2")
    _write_trace(tmp_path, "sess-a", started_at="t1")

    code, out = _run_main(mod, ["--list", "--traces-dir", str(tmp_path)], capsys)
    assert code == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == 2
    ids = {row["id"] for row in data}
    assert ids == {"sess-a", "sess-b"}
    # Most recent first (ended_at DESC)
    assert data[0]["id"] == "sess-b"
    # Expected shape
    row = data[0]
    for key in (
        "session_id",
        "started_at",
        "ended_at",
        "duration_ms",
        "event_count",
        "level",
        "outcome",
    ):
        assert key in row
    assert row["event_count"] == 2 + 3  # turn_count + llm_call_count


def test_list_flag_honours_limit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_module()
    for i in range(5):
        _write_trace(tmp_path, f"sess-{i}", started_at=f"t{i}")

    code, out = _run_main(
        mod, ["--list", "--limit", "2", "--traces-dir", str(tmp_path)], capsys
    )
    assert code == 0
    data = json.loads(out)
    assert len(data) == 2


def test_list_flag_empty_when_dir_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:  # noqa: E501
    mod = _load_module()
    missing = tmp_path / "nope"

    code, out = _run_main(mod, ["--list", "--traces-dir", str(missing)], capsys)
    assert code == 0
    assert json.loads(out) == []


def test_load_flag_prints_full_trace(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_module()
    _write_trace(tmp_path, "sess-1")

    code, out = _run_main(
        mod, ["--load", "sess-1", "--traces-dir", str(tmp_path)], capsys
    )
    assert code == 0
    data = json.loads(out)
    assert data["summary"]["session_id"] == "sess-1"
    assert len(data["events"]) == 2


def test_load_flag_returns_error_when_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_module()
    # Empty dir so load raises TraceNotFoundError inside main()
    tmp_path.mkdir(parents=True, exist_ok=True)

    code = mod.main(["--load", "ghost", "--traces-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "ghost" in captured.err or "not found" in captured.err.lower()
