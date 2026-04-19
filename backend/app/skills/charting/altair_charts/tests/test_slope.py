# backend/app/skills/altair_charts/tests/test_slope.py
from __future__ import annotations

import pandas as pd


def test_slope_chart_has_line_segments() -> None:
    from app.skills.charting.altair_charts.pkg.slope import slope

    df = pd.DataFrame(
        {
            "item": ["A", "A", "B", "B", "C", "C"],
            "period": ["before", "after"] * 3,
            "value": [10, 14, 8, 6, 12, 12],
        }
    )
    chart = slope(df, category="item", period="period", value="value")
    spec = chart.to_dict()
    assert "layer" in spec
    marks = {
        (layer.get("mark", {}).get("type") if isinstance(layer.get("mark"), dict) else layer.get("mark"))  # noqa: E501
        for layer in spec["layer"]
    }
    assert "line" in marks
