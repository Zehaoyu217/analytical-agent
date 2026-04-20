"""Tests for /api/sb/pipeline and /api/sb/maintain routes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config as app_config
from app.api import sb_pipeline as sb_pipeline_module


@pytest.fixture
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / "digests").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    (home / ".sb").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    return home


@pytest.fixture
def client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


def test_pipeline_status_empty_state(sb_home: Path, client: TestClient) -> None:
    resp = client.get("/api/sb/pipeline/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    for phase in ("ingest", "digest", "maintain"):
        assert body[phase] == {"last_run_at": None, "result": None}


def test_pipeline_status_reads_persisted_slot(
    sb_home: Path, client: TestClient
) -> None:
    state_path = sb_home / ".sb" / ".state" / "pipeline.json"
    state_path.parent.mkdir()
    state_path.write_text(
        json.dumps({
            "ingest": {"last_run_at": "2026-04-19T00:00:00Z", "result": {"sources_added": 7}},
            "digest": {"last_run_at": None, "result": None},
            "maintain": {"last_run_at": None, "result": None},
        }),
        encoding="utf-8",
    )
    body = client.get("/api/sb/pipeline/status").json()
    assert body["ingest"]["result"] == {"sources_added": 7}


def test_pipeline_status_404_when_disabled(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    assert client.get("/api/sb/pipeline/status").status_code == 404


def test_maintain_run_returns_summary(
    sb_home: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools import sb_pipeline_state

    def _fake_run_maintain(_cfg: object) -> dict[str, object]:
        summary = {
            "lint_errors": 0,
            "lint_warnings": 1,
            "lint_info": 0,
            "open_contradictions": 0,
            "stale_abstracts": [],
            "stale_count": 0,
            "analytics_rebuilt": True,
            "habit_proposals": 0,
            "fts_bytes_before": 0,
            "fts_bytes_after": 0,
            "duck_bytes_before": 0,
            "duck_bytes_after": 0,
        }
        sb_pipeline_state.write_phase(sb_pipeline_module._cfg(), "maintain", summary)
        return summary

    monkeypatch.setattr(sb_pipeline_state, "run_maintain", _fake_run_maintain)

    resp = client.post("/api/sb/maintain/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["result"]["lint_warnings"] == 1

    status = client.get("/api/sb/pipeline/status").json()
    assert status["maintain"]["result"]["lint_warnings"] == 1


def test_maintain_run_surfaces_errors_as_500(
    sb_home: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools import sb_pipeline_state

    def _boom(_cfg: object) -> dict[str, object]:
        raise RuntimeError("runner exploded")

    monkeypatch.setattr(sb_pipeline_state, "run_maintain", _boom)
    resp = client.post("/api/sb/maintain/run")
    assert resp.status_code == 500
    assert "maintain_run_failed" in resp.json()["detail"]
