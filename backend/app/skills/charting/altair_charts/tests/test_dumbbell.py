# backend/app/skills/altair_charts/tests/test_dumbbell.py
from __future__ import annotations

import pandas as pd


def test_dumbbell_has_two_points_and_connecting_rule() -> None:
    from app.skills.charting.altair_charts.pkg.dumbbell import dumbbell

    df = pd.DataFrame(
        {"item": ["A", "B", "C"], "before": [5.0, 4.0, 6.0], "after": [7.0, 9.0, 3.0]}
    )
    chart = dumbbell(df, category="item", start="before", end="after")
    spec = chart.to_dict()
    assert "layer" in spec
    marks = [
        (layer.get("mark", {}).get("type") if isinstance(layer.get("mark"), dict) else layer.get("mark"))  # noqa: E501
        for layer in spec["layer"]
    ]
    assert marks.count("point") == 2
    assert "rule" in marks
