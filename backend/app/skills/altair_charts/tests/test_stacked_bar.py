# backend/app/skills/altair_charts/tests/test_stacked_bar.py
from __future__ import annotations

import pandas as pd


def test_stacked_bar_default_stack_is_zero() -> None:
    from app.skills.altair_charts.pkg.stacked_bar import stacked_bar

    df = pd.DataFrame(
        {
            "region": ["N", "N", "S", "S"],
            "product": ["A", "B", "A", "B"],
            "revenue": [10.0, 5.0, 9.0, 7.0],
        }
    )
    chart = stacked_bar(df, x="region", y="revenue", category="product")
    spec = chart.to_dict()
    assert spec["encoding"]["y"]["stack"] == "zero"


def test_stacked_bar_percent_normalizes() -> None:
    from app.skills.altair_charts.pkg.stacked_bar import stacked_bar

    df = pd.DataFrame(
        {"region": ["N", "S"], "product": ["A", "A"], "revenue": [10.0, 9.0]}
    )
    chart = stacked_bar(df, x="region", y="revenue", category="product", mode="percent")
    spec = chart.to_dict()
    assert spec["encoding"]["y"]["stack"] == "normalize"
