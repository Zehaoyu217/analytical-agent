# backend/app/skills/data_profiler/tests/test_missingness.py
from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_flags_missing_over_50_percent(heavy_missing_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.missingness import run

    result = run(heavy_missing_df)
    kinds = {(r.kind, r.severity) for r in result["risks"]}
    assert ("missing_over_threshold", "BLOCKER") in kinds
    assert any(r.columns == ("email",) for r in result["risks"] if r.kind == "missing_over_threshold")


def test_flags_co_occurrence_when_columns_missing_together() -> None:
    from app.skills.data_profiler.pkg.sections.missingness import run

    df = pd.DataFrame(
        {"a": [None, None, 3.0, 4.0, 5.0], "b": [None, None, 3.0, 4.0, 5.0]}
    )
    result = run(df)
    kinds = {r.kind for r in result["risks"]}
    assert "missing_co_occurrence" in kinds
