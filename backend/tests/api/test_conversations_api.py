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


def test_patch_pinned_persists(client: TestClient) -> None:
    conv = client.post("/api/conversations", json={"title": "x"}).json()
    cid = conv["id"]
    assert conv["pinned"] is False

    r = client.patch(f"/api/conversations/{cid}", json={"pinned": True})
    assert r.status_code == 200
    assert r.json()["pinned"] is True

    # Persists across reload.
    again = client.get(f"/api/conversations/{cid}").json()
    assert again["pinned"] is True

    # And shows in summary.
    summaries = client.get("/api/conversations").json()
    assert summaries[0]["pinned"] is True


def test_patch_freeze_persists_and_blocks_appends(client: TestClient) -> None:
    conv = client.post("/api/conversations", json={"title": "x"}).json()
    cid = conv["id"]
    assert conv["frozen_at"] is None

    ts = time.time()
    r = client.patch(f"/api/conversations/{cid}", json={"frozen_at": ts})
    assert r.status_code == 200
    assert r.json()["frozen_at"] == pytest.approx(ts, abs=1)

    # Append now blocked with 409.
    r2 = client.post(
        f"/api/conversations/{cid}/turns",
        json={"role": "user", "content": "after-freeze"},
    )
    assert r2.status_code == 409
    assert "frozen" in r2.json()["detail"]


def test_patch_freeze_is_one_way(client: TestClient) -> None:
    conv = client.post("/api/conversations", json={"title": "x"}).json()
    cid = conv["id"]
    client.patch(f"/api/conversations/{cid}", json={"frozen_at": time.time()})
    frozen = client.get(f"/api/conversations/{cid}").json()
    original_frozen_at = frozen["frozen_at"]

    # Sending null/None does not unfreeze; sending a new value is ignored.
    r = client.patch(f"/api/conversations/{cid}", json={"frozen_at": None})
    assert r.status_code == 200
    assert client.get(f"/api/conversations/{cid}").json()["frozen_at"] == original_frozen_at


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


# ── Bulk delete ──────────────────────────────────────────────────────────────


def _create_conv(client: TestClient, title: str) -> dict:
    r = client.post("/api/conversations", json={"title": title})
    assert r.status_code == 200
    return r.json()


def test_bulk_delete_no_filter_wipes_all_unprotected(client: TestClient) -> None:
    a = _create_conv(client, "a")
    b = _create_conv(client, "b")
    c = _create_conv(client, "c")

    r = client.post("/api/conversations/bulk-delete", json={})
    assert r.status_code == 200
    body = r.json()
    assert set(body["deleted_ids"]) == {a["id"], b["id"], c["id"]}
    assert body["preserved_count"] == 0

    remaining = client.get("/api/conversations").json()
    assert remaining == []


def test_bulk_delete_preserves_pinned_by_default(client: TestClient) -> None:
    keep = _create_conv(client, "keep")
    drop = _create_conv(client, "drop")
    client.patch(f"/api/conversations/{keep['id']}", json={"pinned": True})

    r = client.post("/api/conversations/bulk-delete", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_ids"] == [drop["id"]]
    assert body["preserved_count"] == 1

    remaining = {c["id"] for c in client.get("/api/conversations").json()}
    assert remaining == {keep["id"]}


def test_bulk_delete_include_pinned_removes_pinned(client: TestClient) -> None:
    conv = _create_conv(client, "pinned")
    client.patch(f"/api/conversations/{conv['id']}", json={"pinned": True})

    r = client.post(
        "/api/conversations/bulk-delete",
        json={"include_pinned": True},
    )
    assert r.status_code == 200
    assert r.json()["deleted_ids"] == [conv["id"]]
    assert client.get("/api/conversations").json() == []


def test_bulk_delete_preserves_frozen_by_default(client: TestClient) -> None:
    frozen = _create_conv(client, "frozen")
    drop = _create_conv(client, "drop")
    client.patch(
        f"/api/conversations/{frozen['id']}",
        json={"frozen_at": time.time()},
    )

    r = client.post("/api/conversations/bulk-delete", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_ids"] == [drop["id"]]
    assert body["preserved_count"] == 1


def test_bulk_delete_older_than_filter(client: TestClient) -> None:
    """Only conversations with updated_at < older_than are eligible."""
    old = _create_conv(client, "old")
    # Force a gap so the second conversation's updated_at is strictly later.
    time.sleep(0.05)
    cutoff = time.time()
    time.sleep(0.05)
    new = _create_conv(client, "new")

    r = client.post(
        "/api/conversations/bulk-delete",
        json={"older_than": cutoff},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_ids"] == [old["id"]]
    assert body["preserved_count"] == 1

    remaining = {c["id"] for c in client.get("/api/conversations").json()}
    assert remaining == {new["id"]}


def test_bulk_delete_on_empty_dir_returns_empty(client: TestClient) -> None:
    r = client.post("/api/conversations/bulk-delete", json={})
    assert r.status_code == 200
    assert r.json() == {"deleted_ids": [], "preserved_count": 0}
