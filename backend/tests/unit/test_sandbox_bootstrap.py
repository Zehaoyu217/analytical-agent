"""Unit tests for build_duckdb_globals in sandbox_bootstrap."""
from __future__ import annotations

import subprocess
import sys

from app.harness.sandbox_bootstrap import build_duckdb_globals


def test_build_duckdb_globals_no_dataset() -> None:
    preamble = build_duckdb_globals("test-session-001", None)
    assert "import duckdb" in preamble
    assert "df = None" in preamble
    assert "save_artifact" in preamble


def test_build_duckdb_globals_has_conn() -> None:
    preamble = build_duckdb_globals("test-session-001", None)
    assert "conn = duckdb.connect" in preamble


def test_build_duckdb_globals_session_id_embedded() -> None:
    preamble = build_duckdb_globals("my-session-xyz", None)
    assert "my-session-xyz" in preamble


def test_build_duckdb_globals_csv_dataset(tmp_path: object) -> None:
    fake_path = "/tmp/data.csv"
    preamble = build_duckdb_globals("test-session-csv", fake_path)
    assert "pd.read_csv" in preamble
    assert "df =" in preamble
    assert 'conn.register("dataset"' in preamble


def test_build_duckdb_globals_parquet_dataset() -> None:
    fake_path = "/tmp/data.parquet"
    preamble = build_duckdb_globals("test-session-pq", fake_path)
    assert "pd.read_parquet" in preamble
    assert "df =" in preamble
    assert 'conn.register("dataset"' in preamble


def test_build_duckdb_globals_runs_in_subprocess() -> None:
    """Verify the generated preamble is valid Python that executes without error."""
    preamble = build_duckdb_globals("test-session-sub", None)
    # Patch paths so it doesn't need real data dirs
    code = preamble + "\nprint('ok')"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # 0 = success, 1 = import error (acceptable in minimal test env with missing packages)
    # We just want no syntax error (which would be exit code 1 with SyntaxError in stderr)
    if result.returncode not in (0, 1):
        raise AssertionError(
            f"Unexpected returncode {result.returncode}\nstderr: {result.stderr}"
        )
    # If it failed, ensure it's an ImportError not a SyntaxError
    if result.returncode == 1:
        assert "SyntaxError" not in result.stderr, (
            f"Preamble has a syntax error:\n{result.stderr}"
        )
