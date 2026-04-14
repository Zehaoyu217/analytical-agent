from __future__ import annotations

from pathlib import Path

import duckdb


def test_seed_creates_all_tables(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    counts = seed_all(db_path)
    assert counts["customers"] == 200
    assert 380 <= counts["accounts"] <= 420
    assert 4900 <= counts["transactions"] <= 5100
    assert counts["loans"] == 80
    assert counts["daily_rates"] == 365


def test_seed_is_idempotent(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    counts1 = seed_all(db_path)
    counts2 = seed_all(db_path)
    assert counts1 == counts2


def test_anomalies_are_flagged(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    seed_all(db_path)
    con = duckdb.connect(str(db_path))
    flagged = con.execute(
        "SELECT COUNT(*) FROM transactions WHERE is_flagged"
    ).fetchone()
    con.close()
    assert flagged is not None
    # 1 (A1) + 12 (A2) + 4 (A3) + 1 (A4) + 1 (A5) + 8 (A6) = 27
    assert flagged[0] == 27


def test_anomalies_in_q3_2025(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    seed_all(db_path)
    con = duckdb.connect(str(db_path))
    result = con.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE is_flagged
        AND txn_date >= '2025-07-01' AND txn_date < '2025-10-01'
    """).fetchone()
    con.close()
    assert result is not None
    assert result[0] == 27  # all anomalies in Q3


def test_credit_score_segment_correlation(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    seed_all(db_path)
    con = duckdb.connect(str(db_path))
    result = con.execute("""
        SELECT segment, AVG(credit_score) AS avg_score
        FROM customers
        GROUP BY segment
        ORDER BY avg_score
    """).fetchall()
    con.close()
    # retail < business < premium
    segments = [row[0] for row in result]
    assert segments.index("retail") < segments.index("premium")


def test_loan_rate_inversely_correlated_with_credit(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    seed_all(db_path)
    con = duckdb.connect(str(db_path))
    result = con.execute("""
        SELECT
            CASE WHEN c.credit_score < 700 THEN 'low' ELSE 'high' END AS bucket,
            AVG(l.interest_rate) AS avg_rate
        FROM loans l
        JOIN customers c ON l.customer_id = c.customer_id
        GROUP BY bucket
    """).fetchall()
    con.close()
    rates = {row[0]: row[1] for row in result}
    assert rates["low"] > rates["high"]


def test_daily_rates_has_two_cuts(tmp_path: Path) -> None:
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    seed_all(db_path)
    con = duckdb.connect(str(db_path))
    result = con.execute("""
        SELECT COUNT(DISTINCT fed_funds_rate)
        FROM daily_rates
    """).fetchone()
    con.close()
    assert result is not None
    assert result[0] == 3  # 5.25, 5.00, 4.75
