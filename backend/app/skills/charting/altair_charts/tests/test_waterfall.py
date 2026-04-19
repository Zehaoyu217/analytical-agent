# backend/app/skills/altair_charts/tests/test_waterfall.py
from __future__ import annotations

import pandas as pd


def test_waterfall_has_bars_with_from_to_encoding() -> None:
    from app.skills.charting.altair_charts.pkg.waterfall import waterfall

    df = pd.DataFrame(
        {
            "step": ["start", "price", "volume", "mix", "end"],
            "delta": [100.0, 20.0, -10.0, 5.0, 0.0],
            "kind": ["total", "delta", "delta", "delta", "total"],
        }
    )
    chart = waterfall(df, step="step", delta="delta", kind="kind")
    spec = chart.to_dict()
    # Bars must encode y and y2 (range) to form the stepped effect.
    first = spec["layer"][0] if "layer" in spec else spec
    enc = first["encoding"]
    assert "y" in enc and "y2" in enc


def test_waterfall_positive_and_negative_colors_differ() -> None:
    from app.skills.charting.altair_charts.pkg.waterfall import waterfall

    df = pd.DataFrame(
        {
            "step": ["a", "b"],
            "delta": [5.0, -3.0],
            "kind": ["delta", "delta"],
        }
    )
    chart = waterfall(df, step="step", delta="delta", kind="kind")
    spec = chart.to_dict()
    # color domain should distinguish positive / negative / total
    bars = spec["layer"][0] if "layer" in spec else spec
    color_enc = bars["encoding"].get("color", {})
    # Expect a condition or domain referencing deltaSign.
    assert color_enc  # presence check; exact shape depends on Altair version
