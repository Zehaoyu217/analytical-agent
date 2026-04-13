# backend/app/skills/altair_charts/pkg/slope.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def slope(
    df: pd.DataFrame,
    category: str,
    period: str,
    value: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (category, period, value) if f not in df.columns]
    if missing:
        raise KeyError(
            f"slope(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    style = resolve_series_style("primary")

    line = (
        alt.Chart(df)
        .mark_line(strokeWidth=style["strokeWidth"], color=style["color"])
        .encode(
            x=alt.X(period, type="nominal", sort=None, title=period),
            y=alt.Y(value, type="quantitative", title=value),
            detail=alt.Detail(category, type="nominal"),
        )
    )
    points = (
        alt.Chart(df)
        .mark_point(filled=True, size=60, color=style["color"])
        .encode(
            x=alt.X(period, type="nominal", sort=None),
            y=alt.Y(value, type="quantitative"),
            detail=alt.Detail(category, type="nominal"),
        )
    )
    labels = (
        alt.Chart(df)
        .mark_text(align="left", dx=6, dy=0)
        .encode(
            x=alt.X(period, type="nominal", sort=None),
            y=alt.Y(value, type="quantitative"),
            detail=alt.Detail(category, type="nominal"),
            text=alt.Text(category, type="nominal"),
        )
    )
    chart = alt.layer(line, points, labels)
    if title:
        chart = chart.properties(title=title)
    return chart
