"""Tests for /api/sb/gardener/* routes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config as app_config


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


class _FakeResult:
    def __init__(
        self,
        *,
        passes_run: list[str],
        proposals_added: int = 0,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
        duration_ms: int = 1,
        errors: list[str] | None = None,
    ) -> None:
        self.passes_run = passes_run
        self.proposals_added = proposals_added
        self.total_tokens = total_tokens
        self.total_cost_usd = total_cost_usd
        self.duration_ms = duration_ms
        self.errors = errors or []


class _FakeEstimate:
    def __init__(self, passes: dict[str, dict[str, float]]) -> None:
        # Matches CostEstimate.passes: name -> PassEstimate-like.
        class _P:
            def __init__(self, tokens: int, cost_usd: float) -> None:
                self.tokens = tokens
                self.cost_usd = cost_usd

        self.passes = {k: _P(int(v["tokens"]), float(v["cost_usd"])) for k, v in passes.items()}

    @property
    def total_tokens(self) -> int:
        return sum(p.tokens for p in self.passes.values())

    @property
    def total_cost_usd(self) -> float:
        return sum(p.cost_usd for p in self.passes.values())


class _FakeRunner:
    def __init__(self, *_, **__) -> None:
        pass

    def run(self, *, dry_run: bool | None = None, only: list[str] | None = None) -> _FakeResult:
        return _FakeResult(
            passes_run=only or ["extract"],
            proposals_added=3,
            total_tokens=1200,
            total_cost_usd=0.012,
            duration_ms=42,
        )

    def estimate(self) -> _FakeEstimate:
        return _FakeEstimate({"extract": {"tokens": 1000, "cost_usd": 0.01}})


def _patch_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import sb_gardener

    monkeypatch.setattr(sb_gardener, "_build_runner", lambda cfg, habits: _FakeRunner())


def test_status_returns_slot_and_habits(sb_home: Path, client: TestClient) -> None:
    resp = client.get("/api/sb/gardener/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["slot"] == {"last_run_at": None, "result": None}
    assert body["habits"]["mode"] == "proposal"
    # Default passes enabled: extract true, dedupe false etc.
    assert body["habits"]["passes"]["extract"] is True
    assert "extract" in body["enabled_passes"]


def test_status_404_when_disabled(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    assert client.get("/api/sb/gardener/status").status_code == 404


def test_run_returns_summary_and_updates_ledger(
    sb_home: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_runner(monkeypatch)

    resp = client.post("/api/sb/gardener/run", json={"passes": ["extract"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["result"]["proposals_added"] == 3
    assert body["result"]["passes_run"] == ["extract"]

    status = client.get("/api/sb/pipeline/status").json()
    assert status["gardener"]["result"]["proposals_added"] == 3


def test_run_dry_run_does_not_write_ledger(
    sb_home: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_runner(monkeypatch)

    resp = client.post("/api/sb/gardener/run", json={"dry_run": True})
    assert resp.status_code == 200
    assert resp.json()["result"]["proposals_added"] == 3

    status = client.get("/api/sb/pipeline/status").json()
    assert status["gardener"] == {"last_run_at": None, "result": None}


def test_run_surfaces_exception_as_500(
    sb_home: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import sb_gardener

    class _Boom:
        def run(self, **_: object) -> None:
            raise RuntimeError("kaboom")

    monkeypatch.setattr(sb_gardener, "_build_runner", lambda cfg, habits: _Boom())
    resp = client.post("/api/sb/gardener/run", json={})
    assert resp.status_code == 500
    assert "gardener_run_failed" in resp.json()["detail"]


def test_habits_patch_merges_and_persists(
    sb_home: Path, client: TestClient
) -> None:
    resp = client.post(
        "/api/sb/gardener/habits",
        json={
            "mode": "autonomous",
            "max_cost_usd_per_run": 1.5,
            "passes": {"dedupe": True},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["gardener"]["mode"] == "autonomous"
    assert body["gardener"]["max_cost_usd_per_run"] == 1.5
    # Merged — extract stays True (default), dedupe now True.
    assert body["gardener"]["passes"]["extract"] is True
    assert body["gardener"]["passes"]["dedupe"] is True

    # Reload via status to confirm disk write.
    status = client.get("/api/sb/gardener/status").json()
    assert status["habits"]["mode"] == "autonomous"
    assert status["habits"]["passes"]["dedupe"] is True


def test_estimate_returns_pass_breakdown(
    sb_home: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_runner(monkeypatch)
    resp = client.get("/api/sb/gardener/estimate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["passes"]["extract"]["tokens"] == 1000
    assert body["total_tokens"] == 1000
    assert body["total_cost_usd"] == pytest.approx(0.01)


def test_log_tail_filters_by_pass(sb_home: Path, client: TestClient) -> None:
    audit_path = sb_home / ".sb" / ".state" / "gardener.log.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"pass": "extract", "line": "a", "accepted": None},
        {"pass": "dedupe", "line": "b", "accepted": None},
        {"pass": "extract", "line": "c", "accepted": True},
    ]
    audit_path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    body = client.get("/api/sb/gardener/log", params={"pass_name": "extract"}).json()
    assert body["ok"] is True
    assert [r["line"] for r in body["rows"]] == ["a", "c"]

    all_body = client.get("/api/sb/gardener/log", params={"n": 50}).json()
    assert len(all_body["rows"]) == 3
