from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_get_returns_defaults_on_cold_start(client: TestClient) -> None:
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    # Default model updated after Anthropic removal — OpenRouter GPT-OSS 120B
    # is now the out-of-the-box route.
    assert body == {
        "theme": "system",
        "model": "openai/gpt-oss-120b:free",
        "send_on_enter": True,
    }


def test_put_roundtrip(client: TestClient) -> None:
    payload = {
        "theme": "dark",
        "model": "claude-opus-4-6",
        "send_on_enter": False,
    }
    r_put = client.put("/api/settings", json=payload)
    assert r_put.status_code == 200
    assert r_put.json() == payload

    r_get = client.get("/api/settings")
    assert r_get.status_code == 200
    assert r_get.json() == payload


def test_put_persists_across_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    first = TestClient(create_app())
    payload = {
        "theme": "light",
        "model": "claude-sonnet-4-6",
        "send_on_enter": True,
    }
    first.put("/api/settings", json=payload)

    second = TestClient(create_app())
    body = second.get("/api/settings").json()
    assert body == payload


def test_put_rejects_invalid_theme(client: TestClient) -> None:
    r = client.put(
        "/api/settings",
        json={"theme": "neon", "model": "x", "send_on_enter": True},
    )
    assert r.status_code == 422
