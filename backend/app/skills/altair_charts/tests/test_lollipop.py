# backend/app/skills/altair_charts/tests/test_lollipop.py
from __future__ import annotations

import pandas as pd


def test_lollipop_has_rule_and_point_layers() -> None:
    from app.skills.altair_charts.pkg.lollipop import lollipop

    df = pd.DataFrame({"item": ["A", "B", "C"], "score": [5.0, 9.0, 3.0]})
    chart = lollipop(df, category="item", value="score")
    spec = chart.to_dict()
    assert "layer" in spec
    marks = {
        (l.get("mark", {}).get("type") if isinstance(l.get("mark"), dict) else l.get("mark"))
        for l in spec["layer"]
    }
    assert "rule" in marks
    assert "point" in marks


def test_lollipop_default_sorts_desc() -> None:
    from app.skills.altair_charts.pkg.lollipop import lollipop

    df = pd.DataFrame({"item": ["A", "B", "C"], "score": [5.0, 9.0, 3.0]})
    chart = lollipop(df, category="item", value="score")
    spec = chart.to_dict()
    first_layer = spec["layer"][0]
    y_enc = first_layer["encoding"]["y"]
    assert y_enc.get("sort", {}).get("order", "descending") == "descending"
