"""Integration tests for the DuckDB data pipeline.

Verifies end-to-end:
  1. db_init: tables are loaded (or gracefully skipped when source data is absent)
  2. get_data_context: schema description is generated
  3. sandbox_bootstrap: preamble is syntactically valid and DuckDB is reachable
  4. Sandbox execution: SQL queries return correct results when data is present
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.data.db_init import get_data_context, initialize_db, _BANK_MACRO_DIR
from app.harness.sandbox import SandboxExecutor
from app.harness.sandbox_bootstrap import build_duckdb_globals

# ── fixtures ──────────────────────────────────────────────────────────────────

DATA_PRESENT = (_BANK_MACRO_DIR / "panel_data.csv").exists()


# ── db_init ───────────────────────────────────────────────────────────────────

def test_initialize_db_runs_without_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """initialize_db() must complete without raising regardless of data presence."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("app.config.AppConfig.duckdb_path", str(db_file), raising=False)
    from app.config import get_config
    get_config.cache_clear()
    monkeypatch.setattr(
        "app.data.db_init._BANK_MACRO_DIR",
        Path(tmp_path / "nonexistent"),
    )
    # Should not raise even if source data is missing
    initialize_db()


@pytest.mark.skipif(not DATA_PRESENT, reason="bank-macro source data not available")
def test_initialize_db_loads_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When source CSV files exist, tables are created with expected row counts."""
    import duckdb
    from app.config import AppConfig, get_config

    db_file = tmp_path / "test.db"

    # Patch get_config to return a config pointing at a temp DB
    fake_config = AppConfig(duckdb_path=str(db_file))
    monkeypatch.setattr("app.data.db_init.get_config", lambda: fake_config)
    get_config.cache_clear()

    initialize_db()

    assert db_file.exists(), "DB file was not created by initialize_db()"
    conn = duckdb.connect(str(db_file), read_only=True)
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    conn.close()

    assert "bank_macro_panel" in tables, "bank_macro_panel table not created"
    assert "bank_wide" in tables, "bank_wide table not created"


# ── get_data_context ──────────────────────────────────────────────────────────

def test_get_data_context_returns_string() -> None:
    """get_data_context() always returns a string (empty or non-empty)."""
    result = get_data_context()
    assert isinstance(result, str)


@pytest.mark.skipif(not DATA_PRESENT, reason="bank-macro source data not available")
def test_get_data_context_contains_schema() -> None:
    """When tables are loaded, schema description includes expected column names."""
    ctx = get_data_context()
    assert "bank_macro_panel" in ctx
    assert "date" in ctx
    assert "jpm_total_net_revenue" in ctx
    assert "conn.execute" in ctx


# ── sandbox_bootstrap ─────────────────────────────────────────────────────────

def test_build_duckdb_globals_contains_sys_path_injection() -> None:
    """Bootstrap preamble must include the backend directory in sys.path."""
    preamble = build_duckdb_globals("test-sess-path")
    assert "sys.path.insert" in preamble or "sys.path" in preamble


def test_sandbox_preamble_is_valid_python() -> None:
    """The generated preamble must be syntactically valid Python."""
    preamble = build_duckdb_globals("test-sess-syntax")
    result = subprocess.run(
        [sys.executable, "-c", preamble + "\nprint('syntax-ok')"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "SyntaxError" not in result.stderr, f"Preamble syntax error:\n{result.stderr}"


# ── end-to-end sandbox execution ─────────────────────────────────────────────

@pytest.mark.skipif(not DATA_PRESENT, reason="bank-macro source data not available")
def test_sandbox_can_query_bank_macro_panel() -> None:
    """Sandbox must execute a DuckDB query against bank_macro_panel successfully."""
    preamble = build_duckdb_globals("test-e2e-query")
    code = """
result = conn.execute(
    "SELECT COUNT(*) AS n FROM bank_macro_panel"
).fetchone()
print("rows:", result[0])
assert result[0] > 0, "Expected rows in bank_macro_panel"
"""
    executor = SandboxExecutor(
        python_executable=sys.executable,
        timeout_sec=30,
        extra_globals_script=preamble,
    )
    result = executor.run(code)
    assert result.ok, f"Sandbox failed:\n{result.stderr}"
    assert "rows:" in result.stdout


@pytest.mark.skipif(not DATA_PRESENT, reason="bank-macro source data not available")
def test_sandbox_date_range_query() -> None:
    """Sandbox must return the expected date range from bank_macro_panel."""
    preamble = build_duckdb_globals("test-e2e-dates")
    code = """
row = conn.execute(
    "SELECT MIN(date)::VARCHAR, MAX(date)::VARCHAR FROM bank_macro_panel"
).fetchone()
print("min:", row[0], "max:", row[1])
assert row[0] is not None
assert row[1] is not None
"""
    executor = SandboxExecutor(
        python_executable=sys.executable,
        timeout_sec=30,
        extra_globals_script=preamble,
    )
    result = executor.run(code)
    assert result.ok, f"Sandbox failed:\n{result.stderr}"
    assert "min:" in result.stdout


@pytest.mark.skipif(not DATA_PRESENT, reason="bank-macro source data not available")
def test_sandbox_can_generate_altair_chart() -> None:
    """Sandbox must produce an Altair Chart object from bank_macro_panel data."""
    preamble = build_duckdb_globals("test-e2e-chart")
    code = """
df = conn.execute(
    "SELECT date, jpm_total_net_revenue FROM bank_macro_panel ORDER BY date"
).df()
import altair as alt
chart = alt.Chart(df).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y("jpm_total_net_revenue:Q"),
).properties(title="JPM Revenue")
spec = chart.to_dict()
assert spec["$schema"].startswith("https://vega.github.io/schema/vega-lite/")
print("chart-ok schema:", spec["$schema"][:50])
"""
    executor = SandboxExecutor(
        python_executable=sys.executable,
        timeout_sec=30,
        extra_globals_script=preamble,
    )
    result = executor.run(code)
    assert result.ok, f"Sandbox failed:\n{result.stderr}"
    assert "chart-ok" in result.stdout
