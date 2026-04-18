"""Tests for /api/skills/telemetry."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import skills_telemetry_api


def _client(tmp: Path) -> TestClient:
    # Override the log path to the tmp fixture.
    skills_telemetry_api._telemetry_path = lambda: tmp  # type: ignore[attr-defined]
    app = FastAPI()
    app.include_router(skills_telemetry_api.router)
    return TestClient(app)


def test_empty_when_log_missing(tmp_path: Path) -> None:
    path = tmp_path / "skills.jsonl"
    resp = _client(path).get("/api/skills/telemetry")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ok": True, "count": 0, "events": []}


def test_returns_events_reverse_chronological(tmp_path: Path) -> None:
    path = tmp_path / "skills.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"actor": "skill:a", "outcome": "ok"},
                {"actor": "skill:b", "outcome": "ok"},
                {"actor": "skill:c", "outcome": "error"},
            ]
        )
    )
    resp = _client(path).get("/api/skills/telemetry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    assert [e["actor"] for e in body["events"]] == [
        "skill:c",
        "skill:b",
        "skill:a",
    ]


def test_limit_respected(tmp_path: Path) -> None:
    path = tmp_path / "skills.jsonl"
    path.write_text(
        "\n".join(json.dumps({"actor": f"skill:{i}"}) for i in range(10))
    )
    resp = _client(path).get("/api/skills/telemetry?limit=3")
    body = resp.json()
    assert body["count"] == 3
    assert [e["actor"] for e in body["events"]] == [
        "skill:9",
        "skill:8",
        "skill:7",
    ]


def test_malformed_lines_skipped(tmp_path: Path) -> None:
    path = tmp_path / "skills.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"actor": "skill:a"}),
                "{not json",
                "",
                json.dumps({"actor": "skill:b"}),
            ]
        )
    )
    resp = _client(path).get("/api/skills/telemetry")
    body = resp.json()
    assert body["count"] == 2
    assert {e["actor"] for e in body["events"]} == {"skill:a", "skill:b"}
