# backend/app/skills/altair_charts/pkg/area_cumulative.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def area_cumulative(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (x, y) if f not in df.columns]
    if missing:
        raise KeyError(
            f"area_cumulative(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    x_type = "temporal" if pd.api.types.is_datetime64_any_dtype(df[x]) else "quantitative"
    style = resolve_series_style("primary")

    chart = (
        alt.Chart(df)
        .transform_window(
            cumulative=f"sum({y})",
            sort=[alt.SortField(field=x, order="ascending")],
        )
        .mark_area(color=style["color"], opacity=0.75)
        .encode(
            x=alt.X(x, type=x_type, title=x),
            y=alt.Y("cumulative:Q", title=f"cumulative {y}"),
        )
    )
    if title:
        chart = chart.properties(title=title)
    return chart
