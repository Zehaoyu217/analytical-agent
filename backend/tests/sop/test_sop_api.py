from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sop.log import write_entry
from app.sop.types import (
    FixApplied,
    IterationLogEntry,
    PreflightResult,
    TriageDecision,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SOP_LOG_DIR", str(tmp_path / "log"))
    monkeypatch.setenv("SOP_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("SOP_BASELINES_DIR", str(tmp_path / "baselines"))
    return TestClient(create_app())


def _entry(session_id: str) -> IterationLogEntry:
    return IterationLogEntry(
        date=session_id[:10],
        session_id=session_id,
        level=3,
        overall_grade_before="C",
        preflight=PreflightResult(evaluation_bias="pass", data_quality="pass", determinism="pass"),
        triage=TriageDecision(bucket="context", evidence=["e"], hypothesis="h"),
        fix=FixApplied(
            ladder_id="context-01", name="n", files_changed=["f"],
            model_used_for_fix="sonnet", cost_bucket="trivial",
        ),
        outcome={"grade_after": "B", "regressions": "none", "iterations": 1, "success": True},
        trace_links={"before": "a.json", "after": "b.json"},
    )


def test_list_sessions_empty(client: TestClient) -> None:
    resp = client.get("/api/sop/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}


def test_list_sessions_returns_written_entries(client: TestClient, tmp_path: Path) -> None:
    write_entry(_entry("2026-04-12-level3-001"), tmp_path / "log")
    resp = client.get("/api/sop/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "2026-04-12-level3-001"


def test_get_session_by_id(client: TestClient, tmp_path: Path) -> None:
    write_entry(_entry("2026-04-12-level3-001"), tmp_path / "log")
    resp = client.get("/api/sop/sessions/2026-04-12-level3-001")
    assert resp.status_code == 200
    assert resp.json()["triage"]["bucket"] == "context"


def test_get_session_missing_returns_404(client: TestClient) -> None:
    resp = client.get("/api/sop/sessions/never-existed")
    assert resp.status_code == 404


def test_list_ladders_returns_nine(client: TestClient) -> None:
    resp = client.get("/api/sop/ladders")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ladders"]) == 9


def test_judge_variance_endpoint_returns_dimension_variance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_variance = {"detection_recall": 0.2, "false_positive_handling": 0.6}
    monkeypatch.setattr(
        "app.api.sop_api.compute_judge_variance",
        lambda trace_id, n: fake_variance,
    )
    resp = client.get("/api/sop/judge-variance/eval-x?n=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["variance"] == fake_variance
    assert data["threshold_exceeded"] == ["false_positive_handling"]
