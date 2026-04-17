from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    health = tmp_path / "docs" / "health"
    health.mkdir(parents=True)
    (health / "latest.md").write_text("# Hello health\n")
    monkeypatch.chdir(tmp_path)
    # create_app() is called fresh per test, so it picks up the chdir
    from app.main import create_app

    return TestClient(create_app())


def test_serves_latest_md(client: TestClient):
    resp = client.get("/static/health/latest.md")
    assert resp.status_code == 200
    assert "Hello health" in resp.text
