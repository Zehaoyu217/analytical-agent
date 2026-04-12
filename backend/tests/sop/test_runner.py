from __future__ import annotations

from typing import Any

import pytest

from app.sop.runner import run_sop
from app.sop.types import FailureReport, Signals


def _report(**overrides: Any) -> FailureReport:
    base: dict[str, Any] = dict(
        level=3, overall_grade="C", dimensions=[],
        signals=Signals(
            token_count=20000, duration_ms=10, compaction_events=3,
            scratchpad_writes=0, tool_errors=0, retries=0,
            subagents_spawned=0, models_used={"haiku": 5, "sonnet": 2},
        ),
        judge_justifications={}, top_failure_signature="x",
        trace_id="x", trace_path="x", diff_vs_baseline=None,
    )
    base.update(overrides)
    return FailureReport(**base)


def test_preflight_failure_short_circuits() -> None:
    result = run_sop(
        report=_report(),
        judge_variance={"detection_recall": 0.9},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    assert result.preflight.evaluation_bias == "fail"
    assert result.triage is None
    assert result.proposal is None
    assert "evaluation_bias" in result.advisory


def test_triage_returns_proposal_with_cheapest_rung() -> None:
    result = run_sop(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    assert result.triage is not None
    assert result.triage.bucket == "context"
    assert result.proposal is not None
    assert result.proposal.id == "context-01"
    assert result.proposal.cost == "trivial"


def test_no_actionable_signal_returns_none_triage() -> None:
    result = run_sop(
        report=_report(signals=Signals(
            token_count=100, duration_ms=10, compaction_events=0,
            scratchpad_writes=5, tool_errors=0, retries=0,
            subagents_spawned=2, models_used={"sonnet": 5, "haiku": 0},
        )),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    assert result.triage is None
    assert result.proposal is None


def test_sop_result_is_json_serializable() -> None:
    result = run_sop(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    dumped = result.model_dump()
    assert "preflight" in dumped and "triage" in dumped and "proposal" in dumped


def test_empty_ladder_returns_advisory(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sop import runner
    from app.sop.types import LadderDefinition

    def fake(bucket: str) -> LadderDefinition:
        return LadderDefinition(bucket=bucket, description="x", triage_signals=[], ladder=[])

    monkeypatch.setattr(runner, "load_ladder", fake)
    result = runner.run_sop(
        report=_report(), judge_variance={},
        seed_fingerprint_matches=True, rerun_grades=["B", "B"],
    )
    assert result.triage is not None
    assert result.proposal is None
    assert "empty" in result.advisory.lower()


def test_unknown_bucket_returns_advisory(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sop import runner

    def fake(bucket: str) -> object:
        raise FileNotFoundError(f"no ladder for {bucket}")

    monkeypatch.setattr(runner, "load_ladder", fake)
    result = runner.run_sop(
        report=_report(), judge_variance={},
        seed_fingerprint_matches=True, rerun_grades=["B", "B"],
    )
    assert result.triage is not None
    assert result.proposal is None
    assert "no ladder" in result.advisory.lower()
