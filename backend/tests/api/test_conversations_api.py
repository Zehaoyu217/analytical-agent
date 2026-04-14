from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_list_empty_on_cold_start(client: TestClient) -> None:
    r = client.get("/api/conversations")
    assert r.status_code == 200
    assert r.json() == []


def test_create_get_append_list_delete_flow(client: TestClient) -> None:
    # Create
    before = time.time()
    r_create = client.post("/api/conversations", json={"title": "First chat"})
    assert r_create.status_code == 200
    created = r_create.json()
    after = time.time()

    assert created["title"] == "First chat"
    assert created["turns"] == []
    assert len(created["id"]) == 24
    assert all(c in "0123456789abcdef" for c in created["id"])
    assert before - 1 <= created["created_at"] <= after + 1
    assert created["created_at"] == created["updated_at"]

    conv_id = created["id"]

    # Get
    r_get = client.get(f"/api/conversations/{conv_id}")
    assert r_get.status_code == 200
    assert r_get.json()["id"] == conv_id

    # Append turn — timestamp filled server-side; client-supplied value should be ignored.
    r_turn = client.post(
        f"/api/conversations/{conv_id}/turns",
        json={"role": "user", "content": "hello world"},
    )
    assert r_turn.status_code == 200
    body = r_turn.json()
    assert len(body["turns"]) == 1
    turn = body["turns"][0]
    assert turn["role"] == "user"
    assert turn["content"] == "hello world"
    assert isinstance(turn["timestamp"], float)
    assert turn["timestamp"] >= created["created_at"]
    assert body["updated_at"] == turn["timestamp"]

    # Append another
    r_turn2 = client.post(
        f"/api/conversations/{conv_id}/turns",
        json={"role": "assistant", "content": "hi back"},
    )
    assert r_turn2.status_code == 200
    assert len(r_turn2.json()["turns"]) == 2

    # List contains summary
    r_list = client.get("/api/conversations")
    assert r_list.status_code == 200
    summaries = r_list.json()
    assert len(summaries) == 1
    assert summaries[0]["id"] == conv_id
    assert summaries[0]["turn_count"] == 2

    # Delete
    r_del = client.delete(f"/api/conversations/{conv_id}")
    assert r_del.status_code == 200
    assert r_del.json() == {"ok": True}
    assert client.get(f"/api/conversations/{conv_id}").status_code == 404


def test_list_sorted_by_updated_at_desc(client: TestClient) -> None:
    r1 = client.post("/api/conversations", json={"title": "One"})
    r2 = client.post("/api/conversations", json={"title": "Two"})
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    # Bump id1 by appending a turn so it has the most recent updated_at.
    time.sleep(0.01)
    client.post(
        f"/api/conversations/{id1}/turns",
        json={"role": "user", "content": "bump"},
    )

    ordered = client.get("/api/conversations").json()
    assert [s["id"] for s in ordered] == [id1, id2]


def test_get_missing_returns_404(client: TestClient) -> None:
    r = client.get("/api/conversations/nonexistent")
    assert r.status_code == 404


def test_delete_missing_returns_404(client: TestClient) -> None:
    r = client.delete("/api/conversations/nonexistent")
    assert r.status_code == 404


def test_append_to_missing_returns_404(client: TestClient) -> None:
    r = client.post(
        "/api/conversations/missing/turns",
        json={"role": "user", "content": "x"},
    )
    assert r.status_code == 404


def test_invalid_id_returns_400(client: TestClient) -> None:
    # `!` is outside the [A-Za-z0-9_-] regex set, so the regex guard rejects it.
    r = client.get("/api/conversations/bad!id")
    assert r.status_code == 400


def test_create_rejects_empty_title(client: TestClient) -> None:
    r = client.post("/api/conversations", json={"title": ""})
    assert r.status_code == 422


def test_turn_rejects_empty_content(client: TestClient) -> None:
    conv = client.post("/api/conversations", json={"title": "x"}).json()
    r = client.post(
        f"/api/conversations/{conv['id']}/turns",
        json={"role": "user", "content": ""},
    )
    assert r.status_code == 422


def test_turn_rejects_unknown_role(client: TestClient) -> None:
    conv = client.post("/api/conversations", json={"title": "x"}).json()
    r = client.post(
        f"/api/conversations/{conv['id']}/turns",
        json={"role": "root", "content": "hello"},
    )
    assert r.status_code == 422


def test_concurrent_turn_appends_do_not_lose_writes(client: TestClient) -> None:
    """Per-conversation lock serializes read-modify-write on /turns."""
    conv = client.post("/api/conversations", json={"title": "race"}).json()
    conv_id = conv["id"]
    n = 20
    errors: list[BaseException] = []

    def append_one(i: int) -> None:
        try:
            r = client.post(
                f"/api/conversations/{conv_id}/turns",
                json={"role": "user", "content": f"msg-{i}"},
            )
            assert r.status_code == 200
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=append_one, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    final = client.get(f"/api/conversations/{conv_id}").json()
    contents = sorted(t["content"] for t in final["turns"])
    assert len(final["turns"]) == n
    assert contents == sorted(f"msg-{i}" for i in range(n))
