# backend/app/skills/altair_charts/tests/test_area_cumulative.py
from __future__ import annotations

import pandas as pd


def test_area_cumulative_returns_area_with_window() -> None:
    from app.skills.altair_charts.pkg.area_cumulative import area_cumulative

    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6, freq="D"),
            "signups": [1, 2, 1, 3, 2, 4],
        }
    )
    chart = area_cumulative(df, x="date", y="signups")
    spec = chart.to_dict()
    assert spec.get("mark") in ("area", {"type": "area"}) or (
        isinstance(spec.get("mark"), dict) and spec["mark"].get("type") == "area"
    )
    # Cumulative sum transform present
    transforms = spec.get("transform", [])
    assert any("window" in t for t in transforms)
