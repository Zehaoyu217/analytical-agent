from __future__ import annotations

from io import BytesIO
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def _csv_bytes() -> bytes:
    return b"col_a,col_b,col_c\n1,alpha,3.14\n2,beta,2.72\n3,gamma,1.41\n"


def test_upload_csv_creates_table_and_records_dataset(
    client: TestClient, tmp_path: Path,
) -> None:
    conv = client.post("/api/conversations", json={"title": "t"}).json()
    conv_id = conv["id"]

    r = client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={"file": ("sales.csv", BytesIO(_csv_bytes()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["table_name"] == "sales"
    assert body["filename"] == "sales.csv"
    assert body["row_count"] == 3
    col_names = [c["name"] for c in body["columns"]]
    assert col_names == ["col_a", "col_b", "col_c"]

    # Dataset is persisted on the conversation
    fresh = client.get(f"/api/conversations/{conv_id}").json()
    assert len(fresh["datasets"]) == 1
    assert fresh["datasets"][0]["table_name"] == "sales"

    # The DuckDB file actually exists and the table is queryable
    db_path = tmp_path / "user_data" / f"{conv_id}.duckdb"
    assert db_path.exists()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute("SELECT * FROM sales ORDER BY col_a").fetchall()
        assert rows == [(1, "alpha", 3.14), (2, "beta", 2.72), (3, "gamma", 1.41)]
    finally:
        con.close()


def test_upload_sanitizes_table_name(client: TestClient) -> None:
    conv_id = client.post("/api/conversations", json={"title": "t"}).json()["id"]
    r = client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={
            "file": (
                "Sales Q1 2025!.csv",
                BytesIO(_csv_bytes()),
                "text/csv",
            ),
        },
    )
    assert r.status_code == 200
    # Spaces, digits, and symbols collapse to underscores; lowercased.
    assert r.json()["table_name"] == "sales_q1_2025"


def test_upload_dedupes_same_table_name(client: TestClient) -> None:
    conv_id = client.post("/api/conversations", json={"title": "t"}).json()["id"]
    r1 = client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={"file": ("sales.csv", BytesIO(_csv_bytes()), "text/csv")},
    )
    r2 = client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={"file": ("sales.csv", BytesIO(_csv_bytes()), "text/csv")},
    )
    assert r1.json()["table_name"] == "sales"
    assert r2.json()["table_name"] == "sales_2"


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    conv_id = client.post("/api/conversations", json={"title": "t"}).json()["id"]
    r = client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={"file": ("notes.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    assert "unsupported file type" in r.json()["detail"]


def test_delete_dataset_drops_table_and_metadata(client: TestClient) -> None:
    conv_id = client.post("/api/conversations", json={"title": "t"}).json()["id"]
    client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={"file": ("sales.csv", BytesIO(_csv_bytes()), "text/csv")},
    )

    r = client.delete(f"/api/conversations/{conv_id}/datasets/sales")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "table_name": "sales"}

    fresh = client.get(f"/api/conversations/{conv_id}").json()
    assert fresh["datasets"] == []


def test_delete_dataset_404_when_missing(client: TestClient) -> None:
    conv_id = client.post("/api/conversations", json={"title": "t"}).json()["id"]
    r = client.delete(f"/api/conversations/{conv_id}/datasets/nope")
    assert r.status_code == 404


def test_upload_auto_creates_conversation_if_missing(client: TestClient) -> None:
    """Uploads should succeed for a freshly-created local conversation that
    has never been persisted to the backend yet."""
    # NOTE: valid-shape id but nothing backing it on disk — simulates a
    # frontend-local conversation that hasn't hit any other backend endpoint.
    orphan_id = "client-side-only-id-1234"
    r = client.post(
        f"/api/conversations/{orphan_id}/uploads",
        files={"file": ("sales.csv", BytesIO(_csv_bytes()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["table_name"] == "sales"

    # And the Conversation JSON should now exist so subsequent GETs work.
    fresh = client.get(f"/api/conversations/{orphan_id}")
    assert fresh.status_code == 200
    assert fresh.json()["title"] == "New chat"
    assert len(fresh.json()["datasets"]) == 1


def test_injector_emits_datasets_block_after_upload(
    client: TestClient, tmp_path: Path,
) -> None:
    """Smoke test that the system-prompt block renders from the stored metadata."""
    conv_id = client.post("/api/conversations", json={"title": "t"}).json()["id"]
    client.post(
        f"/api/conversations/{conv_id}/uploads",
        files={"file": ("orders.csv", BytesIO(_csv_bytes()), "text/csv")},
    )

    from app.api.chat_api import _load_conversation_datasets

    summaries = _load_conversation_datasets(conv_id)
    assert len(summaries) == 1
    assert summaries[0].table_name == "orders"
    assert summaries[0].row_count == 3
    # Columns are rendered as "name (TYPE)" for the prompt.
    col_strings = list(summaries[0].columns)
    assert any("col_a (BIGINT)" in s for s in col_strings)
