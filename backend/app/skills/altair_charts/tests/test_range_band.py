# backend/app/skills/altair_charts/tests/test_range_band.py
from __future__ import annotations

import pandas as pd


def test_range_band_has_area_and_line_layers() -> None:
    from app.skills.altair_charts.pkg.range_band import range_band

    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "lo": [1, 2, 1, 3, 2],
            "hi": [5, 6, 5, 7, 6],
            "mid": [3, 4, 3, 5, 4],
        }
    )
    chart = range_band(df, x="date", low="lo", high="hi", mid="mid")
    spec = chart.to_dict()
    assert "layer" in spec
    marks = {
        (l.get("mark", {}).get("type") if isinstance(l.get("mark"), dict) else l.get("mark"))
        for l in spec["layer"]
    }
    assert "area" in marks
    assert "line" in marks
