# backend/app/skills/altair_charts/tests/test_slope.py
from __future__ import annotations

import pandas as pd


def test_slope_chart_has_line_segments() -> None:
    from app.skills.altair_charts.pkg.slope import slope

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
        (l.get("mark", {}).get("type") if isinstance(l.get("mark"), dict) else l.get("mark"))
        for l in spec["layer"]
    }
    assert "line" in marks
