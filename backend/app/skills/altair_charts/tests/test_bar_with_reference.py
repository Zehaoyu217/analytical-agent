# backend/app/skills/altair_charts/tests/test_bar_with_reference.py
from __future__ import annotations

import pandas as pd


def test_bar_with_reference_has_rule_layer() -> None:
    from app.skills.altair_charts.pkg.bar_with_reference import bar_with_reference

    df = pd.DataFrame({"region": ["N", "S", "E"], "revenue": [10.0, 12.0, 8.0]})
    chart = bar_with_reference(df, x="region", y="revenue", reference_value=10.0)
    spec = chart.to_dict()
    assert "layer" in spec
    marks = {layer.get("mark", {}).get("type") if isinstance(layer.get("mark"), dict) else layer.get("mark") for layer in spec["layer"]}
    assert "bar" in marks
    assert "rule" in marks


def test_bar_with_reference_rule_is_reference_styled() -> None:
    from app.skills.altair_charts.pkg.bar_with_reference import bar_with_reference

    df = pd.DataFrame({"region": ["N", "S"], "revenue": [10.0, 9.0]})
    chart = bar_with_reference(df, x="region", y="revenue", reference_value=9.5)
    spec = chart.to_dict()
    rule_layer = next(l for l in spec["layer"] if (l.get("mark", {}) or {}).get("type") == "rule" or l.get("mark") == "rule")
    mark = rule_layer["mark"]
    assert isinstance(mark, dict)
    assert mark.get("strokeDash") is not None
