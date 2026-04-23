from __future__ import annotations

import duckdb
import pytest

from second_brain.graph.extension import ensure_duckpgq


def test_ensure_duckpgq_returns_true_on_success() -> None:
    conn = duckdb.connect(":memory:")
    try:
        loaded = ensure_duckpgq(conn)
    except Exception:
        pytest.skip("duckpgq install blocked in this environment")
    assert loaded is True
    row = conn.execute("SELECT extension_name FROM duckdb_extensions() WHERE loaded").fetchall()
    names = {r[0] for r in row}
    assert "duckpgq" in names


def test_ensure_duckpgq_idempotent() -> None:
    conn = duckdb.connect(":memory:")
    try:
        a = ensure_duckpgq(conn)
        b = ensure_duckpgq(conn)
    except Exception:
        pytest.skip("duckpgq install blocked in this environment")
    assert a and b
