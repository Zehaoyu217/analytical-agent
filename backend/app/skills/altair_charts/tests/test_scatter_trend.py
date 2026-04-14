# backend/app/skills/altair_charts/tests/test_scatter_trend.py
from __future__ import annotations

import pandas as pd


def test_scatter_trend_layers_points_and_regression_line() -> None:
    from app.skills.altair_charts.pkg.scatter_trend import scatter_trend

    df = pd.DataFrame({"x": list(range(20)), "y": [i * 2 + 1 for i in range(20)]})
    chart = scatter_trend(df, x="x", y="y")
    spec = chart.to_dict()
    assert "layer" in spec
    marks = {layer.get("mark", {}).get("type") if isinstance(layer.get("mark"), dict) else layer.get("mark") for layer in spec["layer"]}
    assert "point" in marks or "circle" in marks
    assert "line" in marks


def test_scatter_trend_raises_on_non_numeric_axes() -> None:
    import pytest

    from app.skills.altair_charts.pkg.scatter_trend import scatter_trend

    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    with pytest.raises(ValueError, match="numeric"):
        scatter_trend(df, x="x", y="y")
