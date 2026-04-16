from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_list_slash_commands(client: TestClient) -> None:
    r = client.get("/api/slash")
    assert r.status_code == 200
    body = r.json()
    ids = [cmd["id"] for cmd in body]
    assert ids == ["help", "clear", "new", "settings"]
    for cmd in body:
        assert set(cmd.keys()) == {"id", "label", "description"}
        assert cmd["label"].startswith("/")
        assert cmd["description"]


def test_execute_endpoint_removed(client: TestClient) -> None:
    """Slash commands are dispatched client-side; the legacy execute endpoint
    is gone. Posting to it must 404 (FastAPI default for unknown routes)."""
    r = client.post("/api/slash/execute", json={"command_id": "help"})
    assert r.status_code == 404
