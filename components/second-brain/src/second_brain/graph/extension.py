from __future__ import annotations

import duckdb

_REPO_URL = "https://duckpgq.s3.eu-central-1.amazonaws.com"


def ensure_duckpgq(conn: duckdb.DuckDBPyConnection) -> bool:
    """Install + load the DuckPGQ extension. Returns True on success."""
    conn.execute("SET custom_extension_repository = ?", [_REPO_URL])
    try:
        conn.execute("INSTALL duckpgq FROM community")
    except duckdb.Error:
        # Community repo already holds duckpgq in recent DuckDB releases;
        # fall back to direct install without the repository hint.
        conn.execute("INSTALL duckpgq")
    conn.execute("LOAD duckpgq")
    return True
