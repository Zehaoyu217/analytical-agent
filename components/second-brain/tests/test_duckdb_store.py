from __future__ import annotations

from pathlib import Path

from second_brain.store.duckdb_store import DuckStore


def test_creates_tables_in_empty_file(tmp_path: Path) -> None:
    db = tmp_path / "graph.duckdb"
    with DuckStore.open(db) as store:
        store.ensure_schema()
        tables = store.list_tables()
    assert "sources" in tables
    assert "claims" in tables
    assert "edges" in tables


def test_insert_and_query_source(tmp_path: Path) -> None:
    db = tmp_path / "graph.duckdb"
    with DuckStore.open(db) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_a", slug="a", title="A", kind="pdf",
            year=2024, habit_taxonomy="papers/ml",
            content_hash="sha256:0", abstract="abs",
        )
        rows = store.conn.execute("SELECT id, title FROM sources").fetchall()
    assert rows == [("src_a", "A")]


def test_atomic_swap_replaces_file(tmp_path: Path) -> None:
    target = tmp_path / "graph.duckdb"
    staging = tmp_path / "next" / "graph.duckdb"
    staging.parent.mkdir()
    with DuckStore.open(staging) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_x", slug="x", title="X", kind="note",
            year=None, habit_taxonomy=None,
            content_hash="sha256:1", abstract="",
        )
    DuckStore.atomic_swap(staging=staging, target=target)
    assert target.exists()
    assert not staging.exists()
    with DuckStore.open(target) as store:
        rows = store.conn.execute("SELECT id FROM sources").fetchall()
    assert rows == [("src_x",)]
