# backend/app/skills/altair_charts/tests/test_violin.py
from __future__ import annotations

import numpy as np
import pandas as pd


def test_violin_faceted_by_group() -> None:
    from app.skills.altair_charts.pkg.violin import violin

    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "value": np.concatenate([rng.normal(size=80), rng.normal(loc=1.0, size=80)]),
            "group": ["A"] * 80 + ["B"] * 80,
        }
    )
    chart = violin(df, value="value", group="group")
    spec = chart.to_dict()
    transforms = spec.get("spec", spec).get("transform", [])
    assert any("density" in t for t in transforms)
    assert "facet" in spec or spec.get("spec") is not None
