from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_flags_date_gap(date_gap_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.dates import run

    result = run(date_gap_df)
    assert any(r.kind == "date_gaps" for r in result["risks"])


def test_flags_future_dates() -> None:
    from app.skills.data_profiler.pkg.sections.dates import run

    df = pd.DataFrame({"ts": pd.to_datetime(["2099-01-01", "2020-01-01"])})
    result = run(df)
    assert any(r.kind == "date_future" for r in result["risks"])


def test_flags_timezone_naive() -> None:
    from app.skills.data_profiler.pkg.sections.dates import run

    df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01"])})
    result = run(df)
    assert any(r.kind == "timezone_naive" for r in result["risks"])
