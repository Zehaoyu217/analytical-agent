"""Tests for /api/sb REST routes."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import config as app_config
from app.api import sb_api


def _client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(sb_api.router)
    return TestClient(app)


# ─────────────────────── gating ─────────────────────────────────────


def test_stats_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/stats")
    assert resp.status_code == 404


def test_stats_happy_path(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    from app.tools import sb_digest_tools

    monkeypatch.setattr(
        sb_digest_tools,
        "sb_stats",
        lambda _args: {
            "ok": True,
            "stats": {"claims": 10},
            "health": {"score": 88, "grade": "B"},
        },
        raising=False,
    )
    resp = _client().get("/api/sb/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["stats"] == {"claims": 10}
    assert body["health"]["score"] == 88
