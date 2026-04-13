# backend/app/skills/altair_charts/tests/test_grouped_bar.py
from __future__ import annotations

import pandas as pd


def test_grouped_bar_uses_xoffset_for_category() -> None:
    from app.skills.altair_charts.pkg.grouped_bar import grouped_bar

    df = pd.DataFrame(
        {
            "region": ["N", "N", "S", "S"],
            "quarter": ["Q1", "Q2", "Q1", "Q2"],
            "revenue": [10.0, 12.0, 9.0, 11.0],
        }
    )
    chart = grouped_bar(df, x="region", y="revenue", category="quarter")
    spec = chart.to_dict()
    enc = spec["encoding"]
    assert enc["y"]["field"] == "revenue"
    assert enc["color"]["field"] == "quarter"
    assert enc["xOffset"]["field"] == "quarter"


def test_grouped_bar_raises_on_missing_field() -> None:
    from app.skills.altair_charts.pkg.grouped_bar import grouped_bar

    df = pd.DataFrame({"region": ["N"], "revenue": [1.0]})
    try:
        grouped_bar(df, x="region", y="revenue", category="quarter")
    except KeyError as exc:
        assert "quarter" in str(exc)
    else:
        raise AssertionError("expected KeyError")
