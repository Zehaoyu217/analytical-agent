# backend/app/skills/altair_charts/tests/test_actual_vs_forecast.py
from __future__ import annotations

import pandas as pd


def _fake_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=8, freq="ME")
    return pd.DataFrame(
        {
            "date": dates,
            "actual": [100, 102, 104, 108, None, None, None, None],
            "forecast": [None, None, None, 108, 110, 112, 114, 116],
            "lo": [None, None, None, 106, 107, 108, 108, 109],
            "hi": [None, None, None, 110, 113, 116, 120, 123],
        }
    )


def test_actual_vs_forecast_has_three_layers_minimum() -> None:
    from app.skills.charting.altair_charts.pkg.actual_vs_forecast import actual_vs_forecast

    df = _fake_frame()
    chart = actual_vs_forecast(
        df,
        x="date",
        actual="actual",
        forecast="forecast",
        forecast_low="lo",
        forecast_high="hi",
    )
    spec = chart.to_dict()
    assert "layer" in spec
    # band (area) + forecast (line) + actual (line) at minimum
    assert len(spec["layer"]) >= 3


def test_actual_vs_forecast_forecast_dashed() -> None:
    from app.skills.charting.altair_charts.pkg.actual_vs_forecast import actual_vs_forecast

    df = _fake_frame()
    chart = actual_vs_forecast(df, x="date", actual="actual", forecast="forecast")
    spec = chart.to_dict()
    dashed = [
        layer
        for layer in spec["layer"]
        if isinstance(layer.get("mark"), dict) and layer["mark"].get("strokeDash") is not None
    ]
    assert dashed, "expected at least one dashed layer (forecast)"


def test_actual_vs_forecast_raises_if_missing_actual() -> None:
    from app.skills.charting.altair_charts.pkg.actual_vs_forecast import actual_vs_forecast

    df = _fake_frame().drop(columns=["actual"])
    try:
        actual_vs_forecast(df, x="date", actual="actual", forecast="forecast")
    except KeyError as exc:
        assert "actual" in str(exc)
    else:
        raise AssertionError("expected KeyError")
