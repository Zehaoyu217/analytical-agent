from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from second_brain.graph.property_graph import create_property_graph
from second_brain.store.duckdb_store import DuckStore


def _requires_duckpgq() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL duckpgq")
        conn.execute("LOAD duckpgq")
    except duckdb.Error:
        pytest.skip("duckpgq unavailable")


def test_creates_property_graph(tmp_path: Path) -> None:
    _requires_duckpgq()
    db = tmp_path / "g.duckdb"
    with DuckStore.open(db) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_a", slug="a", title="A", kind="note",
            year=None, habit_taxonomy=None,
            content_hash="sha256:1", abstract="",
        )
        store.insert_source(
            id="src_b", slug="b", title="B", kind="note",
            year=None, habit_taxonomy=None,
            content_hash="sha256:2", abstract="",
        )
        store.insert_edge(
            src_id="src_a", dst_id="src_b", relation="cites",
            confidence="extracted", rationale=None, source_markdown="/a",
        )
        ok = create_property_graph(store.conn)
    assert ok is True
    # Verify the graph exists by listing it.
    with DuckStore.open(db) as store:
        from second_brain.graph.extension import ensure_duckpgq
        ensure_duckpgq(store.conn)
        rows = store.conn.execute(
            "SELECT property_graph_name FROM duckpgq_property_graphs()"
        ).fetchall()
    names = {r[0] for r in rows}
    assert "sb_graph" in names
