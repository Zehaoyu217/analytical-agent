"""Initialize the shared DuckDB and load default datasets on startup.

On first launch (or when tables are absent), ingests the bank-macro-analysis
CSVs into data/duckdb/analytical.db so every sandbox session sees them.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import duckdb

from app.config import get_config

logger = logging.getLogger(__name__)

_BANK_MACRO_DIR = Path(
    os.getenv(
        "BANK_MACRO_DATA_DIR",
        "/Users/jay/Developer/bank-macro-analysis/data/processed",
    )
)

_BANK_REVENUES_DIR = Path(
    os.getenv(
        "BANK_REVENUES_DATA_DIR",
        "/Users/jay/Developer/bank-revenues/data/processed",
    )
)

_DEFAULT_DATASETS: list[tuple[str, str]] = [
    ("panel_data.csv", "bank_macro_panel"),   # macro + bank revenue (main table)
    ("bank_wide.csv", "bank_wide"),            # bank-only wide format
]

_BANK_REVENUE_DATASETS: list[tuple[str, str]] = [
    ("bank_segment_revenue.csv", "bank_segment_revenue"),  # quarterly IB/FICC/Equities by bank
]


def initialize_db() -> None:
    """Create the DuckDB file and ingest default datasets if not already loaded."""
    config = get_config()
    db_path = Path(config.duckdb_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        existing = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
        macro_datasets = _DEFAULT_DATASETS if _BANK_MACRO_DIR.exists() else []
        if not _BANK_MACRO_DIR.exists():
            logger.info("Bank-macro data dir not found (%s) — skipping macro datasets", _BANK_MACRO_DIR)
        for filename, table_name in macro_datasets:
            file_path = _BANK_MACRO_DIR / filename
            if not file_path.exists():
                logger.warning("Default dataset not found: %s", file_path)
                continue
            if table_name in existing:
                logger.debug("Table '%s' already loaded — skipping", table_name)
                continue
            conn.execute(
                f'CREATE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(\'{file_path}\')'
            )
            count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]  # type: ignore[index]
            logger.info("Loaded default table '%s': %d rows", table_name, count)

        for filename, table_name in _BANK_REVENUE_DATASETS:
            file_path = _BANK_REVENUES_DIR / filename
            if not file_path.exists():
                logger.warning("Bank revenue dataset not found: %s", file_path)
                continue
            if table_name in existing:
                logger.debug("Table '%s' already loaded — skipping", table_name)
                continue
            conn.execute(
                f'CREATE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(\'{file_path}\')'
            )
            count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]  # type: ignore[index]
            logger.info("Loaded default table '%s': %d rows", table_name, count)
    finally:
        conn.close()


# Date column candidates — checked in order; first match wins per table.
_DATE_COL_CANDIDATES = ("date", "txn_date", "rate_date", "opened_date", "origination_date", "join_date")


def _try_date_range(conn: duckdb.DuckDBPyConnection, tbl: str, col_names: list[str]) -> tuple[object, object] | None:
    """Return (min, max) for the first recognised date column, or None."""
    for col in _DATE_COL_CANDIDATES:
        if col in col_names:
            try:
                row = conn.execute(f'SELECT MIN("{col}"), MAX("{col}") FROM "{tbl}"').fetchone()
                return row if row else None
            except Exception:
                pass
    return None


def get_data_context() -> str:
    """Return a rich schema description for the system prompt.

    Works with any DuckDB database — discovers tables and columns dynamically.
    Injects example queries if recognisable table names are found.
    """
    config = get_config()
    db_path = Path(config.duckdb_path)
    if not db_path.exists():
        return ""
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if not tables:
            conn.close()
            return ""

        lines: list[str] = [
            "## Available Data (DuckDB)",
            f"Database: {db_path.name}",
            "Access via `conn.execute(sql).df()` — `conn` is pre-connected.",
            "",
        ]

        for tbl in tables:
            try:
                cols = conn.execute(f'DESCRIBE "{tbl}"').fetchall()
                col_names = [c[0] for c in cols]
                count = conn.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]  # type: ignore[index]
                date_range = _try_date_range(conn, tbl, col_names)

                if date_range and date_range[0] is not None:
                    lines.append(f"### {tbl}  ({count:,} rows, {date_range[0]} → {date_range[1]})")
                else:
                    lines.append(f"### {tbl}  ({count:,} rows)")

                lines.append(f"  Columns: {', '.join(col_names)}")
                lines.append("")
            except Exception:
                lines.append(f"### {tbl}")
                lines.append("")

        # Inject eval-dataset example queries when recognisable tables are present
        tbl_set = set(tables)
        if {"customers", "accounts", "transactions"}.issubset(tbl_set):
            lines += [
                "### Example queries",
                "```sql",
                "-- Customer segment breakdown",
                "SELECT segment, COUNT(*) AS n, AVG(credit_score) AS avg_score",
                "FROM customers GROUP BY segment ORDER BY n DESC;",
                "",
                "-- Flagged transactions with account and customer info",
                "SELECT t.txn_id, t.txn_date, t.amount, t.category, t.counterparty,",
                "       c.name, c.segment",
                "FROM transactions t",
                "JOIN accounts a ON t.account_id = a.account_id",
                "JOIN customers c ON a.customer_id = c.customer_id",
                "WHERE t.is_flagged ORDER BY ABS(t.amount) DESC LIMIT 10;",
                "",
                "-- Average loan rate by type and credit score band",
                "SELECT loan_type,",
                "       CASE WHEN l.interest_rate < 8 THEN 'low'",
                "            WHEN l.interest_rate < 14 THEN 'mid' ELSE 'high' END AS rate_band,",
                "       COUNT(*) AS n",
                "FROM loans l GROUP BY loan_type, rate_band ORDER BY loan_type, rate_band;",
                "```",
            ]
        elif {"bank_macro_panel", "bank_wide"}.intersection(tbl_set):
            lines += [
                "### Example queries",
                "```sql",
                "-- All banks' quarterly revenue (most recent 4 quarters)",
                "SELECT date, jpm_total_net_revenue, bac_total_net_revenue,",
                "       gs_total_net_revenue, ms_total_net_revenue, c_total_net_revenue",
                "FROM bank_wide ORDER BY date DESC LIMIT 4;",
                "```",
            ]

        if "bank_segment_revenue" in tbl_set:
            lines += [
                "### bank_segment_revenue — key columns",
                "  ticker: GS | JPM | MS | BAC | C",
                "  date: quarter-end date (YYYY-MM-DD)",
                "  ficc_total: Fixed Income, Currencies & Commodities trading revenue ($M)",
                "  eq_total: Equities trading revenue ($M)",
                "  ib_total: Total Investment Banking fees ($M)",
                "  ib_advisory: M&A / Advisory fees ($M)",
                "  ib_debt_uw: Debt underwriting fees ($M)",
                "  ib_equity_uw: Equity underwriting fees ($M)",
                "",
                "### Example queries (bank_segment_revenue)",
                "```sql",
                "-- FICC revenue comparison across banks (last 8 quarters)",
                "SELECT date, ticker, ficc_total, eq_total, ib_total",
                "FROM bank_segment_revenue",
                "WHERE date >= (SELECT MAX(date) - INTERVAL 2 YEAR FROM bank_segment_revenue)",
                "ORDER BY ticker, date;",
                "",
                "-- GS vs JPM IB fee market share over time",
                "SELECT date,",
                "       SUM(CASE WHEN ticker='GS'  THEN ib_total END) AS gs_ib,",
                "       SUM(CASE WHEN ticker='JPM' THEN ib_total END) AS jpm_ib",
                "FROM bank_segment_revenue",
                "WHERE ib_total IS NOT NULL",
                "GROUP BY date ORDER BY date DESC LIMIT 20;",
                "```",
            ]

        conn.close()
        return "\n".join(lines)
    except Exception as exc:
        logger.debug("get_data_context failed: %s", exc)
        return ""
