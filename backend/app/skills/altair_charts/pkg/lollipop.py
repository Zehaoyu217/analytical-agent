# backend/app/skills/altair_charts/pkg/lollipop.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import ensure_theme_registered


def lollipop(
    df: pd.DataFrame,
    category: str,
    value: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (category, value) if f not in df.columns]
    if missing:
        raise KeyError(
            f"lollipop(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    sort = alt.Sort(field=value, op="sum", order="descending")
    base = alt.Chart(df).encode(
        y=alt.Y(category, type="nominal", sort=sort, title=category),
    )
    stem = base.mark_rule(strokeWidth=1.5).encode(
        x=alt.X(f"datum.{value}:Q", title=value) if False else alt.X(value, type="quantitative", title=value),
        x2=alt.datum(0),
    )
    head = base.mark_point(filled=True, size=110).encode(
        x=alt.X(value, type="quantitative", title=value),
    )
    chart = alt.layer(stem, head)
    if title:
        chart = chart.properties(title=title)
    return chart
