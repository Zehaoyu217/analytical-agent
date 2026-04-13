# backend/app/skills/altair_charts/pkg/dumbbell.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def dumbbell(
    df: pd.DataFrame,
    category: str,
    start: str,
    end: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (category, start, end) if f not in df.columns]
    if missing:
        raise KeyError(
            f"dumbbell(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    start_style = resolve_series_style("ghost")
    end_style = resolve_series_style("actual")
    connector_style = resolve_series_style("reference")

    base = alt.Chart(df).encode(
        y=alt.Y(category, type="nominal", title=category, sort="-x"),
    )
    rule = base.mark_rule(
        color=connector_style["color"],
        strokeWidth=1.2,
    ).encode(
        x=alt.X(start, type="quantitative", title=""),
        x2=alt.X2(end),
    )
    p_start = base.mark_point(
        filled=True, size=90, color=start_style["color"]
    ).encode(x=alt.X(start, type="quantitative"))
    p_end = base.mark_point(
        filled=True, size=110, color=end_style["color"]
    ).encode(x=alt.X(end, type="quantitative"))

    chart = alt.layer(rule, p_start, p_end)
    if title:
        chart = chart.properties(title=title)
    return chart
