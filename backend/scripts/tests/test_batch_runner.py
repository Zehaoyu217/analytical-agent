"""Unit tests for BatchRunner (H5.T2).

Note: batch_runner uses late (inside-function) imports to keep the module
importable without the full backend.  For mocking we patch at the source
module level (``app.harness.*``) — these patches are picked up when the
late imports execute during the test.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.batch_runner import BatchRunner


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_loop_outcome(text: str = "result", steps: int = 3) -> MagicMock:
    outcome = MagicMock()
    outcome.final_text = text
    outcome.steps = steps
    return outcome


def _mock_session_db() -> MagicMock:
    db = MagicMock()
    db.create_session.return_value = None
    db.finalize_session.return_value = None
    return db


def _patch_all(runner: BatchRunner, mock_db: MagicMock, mock_outcome: MagicMock):
    """Context manager stack that neutralises all external IO in run_one."""
    import contextlib  # noqa: PLC0415
    return contextlib.ExitStack()


# ── test_batch_runner_processes_all_prompts ───────────────────────────────────

def test_batch_runner_processes_all_prompts(tmp_path: Path):
    prompts = ["prompt A", "prompt B", "prompt C"]
    output = tmp_path / "out.jsonl"
    mock_db = _mock_session_db()
    mock_outcome = _mock_loop_outcome()

    runner = BatchRunner(max_steps=4)

    # Patch the late-imported symbols at their source locations so the
    # runtime `from X import Y` picks up the mock when it executes.
    with (
        patch.object(runner, "_build_client", return_value=MagicMock()),
        patch.object(runner, "_build_system", return_value="sys"),
        patch("app.harness.wiring.get_session_db", return_value=mock_db),
        patch("app.harness.loop.AgentLoop") as MockLoop,
    ):
        MockLoop.return_value.run.return_value = mock_outcome
        summary = runner.run(prompts, output)

    assert summary.total == 3
    assert summary.completed == 3
    assert summary.failed == 0
    lines = [l for l in output.read_text().splitlines() if l.strip()]
    assert len(lines) == 3


# ── test_checkpoint_resume_skips_completed_indices ────────────────────────────

def test_checkpoint_resume_skips_completed_indices(tmp_path: Path):
    prompts = ["p0", "p1", "p2", "p3", "p4"]
    output = tmp_path / "out.jsonl"
    checkpoint = output.with_suffix(".checkpoint.json")

    # Pre-populate checkpoint: indices 0, 1, 2 already completed
    checkpoint.write_text(json.dumps({"completed": [0, 1, 2]}))

    mock_db = _mock_session_db()
    mock_outcome = _mock_loop_outcome()

    runner = BatchRunner(max_steps=4)

    with (
        patch.object(runner, "_build_client", return_value=MagicMock()),
        patch.object(runner, "_build_system", return_value="sys"),
        patch("app.harness.wiring.get_session_db", return_value=mock_db),
        patch("app.harness.loop.AgentLoop") as MockLoop,
    ):
        MockLoop.return_value.run.return_value = mock_outcome
        summary = runner.run(prompts, output, resume=True)

    # Only indices 3 and 4 should have been processed
    assert summary.completed == 2
    lines = [l for l in output.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    result_indices = sorted(json.loads(l)["index"] for l in lines)
    assert result_indices == [3, 4]


# ── test_output_jsonl_is_valid ────────────────────────────────────────────────

def test_output_jsonl_is_valid(tmp_path: Path):
    prompts = ["Tell me about data analysis"]
    output = tmp_path / "out.jsonl"
    mock_db = _mock_session_db()
    mock_outcome = _mock_loop_outcome(text="Great analysis", steps=5)

    runner = BatchRunner(max_steps=4)

    with (
        patch.object(runner, "_build_client", return_value=MagicMock()),
        patch.object(runner, "_build_system", return_value="sys"),
        patch("app.harness.wiring.get_session_db", return_value=mock_db),
        patch("app.harness.loop.AgentLoop") as MockLoop,
    ):
        MockLoop.return_value.run.return_value = mock_outcome
        runner.run(prompts, output)

    lines = [l for l in output.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    result = json.loads(lines[0])
    assert {"index", "prompt", "session_id", "final_text", "steps", "ok"} <= result.keys()
    assert result["ok"] is True
    assert result["steps"] == 5
