# backend/app/skills/altair_charts/pkg/range_band.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def range_band(
    df: pd.DataFrame,
    x: str,
    low: str,
    high: str,
    mid: str | None = None,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    required = [x, low, high] + ([mid] if mid else [])
    missing = [f for f in required if f not in df.columns]
    if missing:
        raise KeyError(
            f"range_band(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    x_type = "temporal" if pd.api.types.is_datetime64_any_dtype(df[x]) else "quantitative"

    band_style = resolve_series_style("scenario")
    band = (
        alt.Chart(df)
        .mark_area(opacity=0.35, color=band_style["color"])
        .encode(
            x=alt.X(x, type=x_type, title=x),
            y=alt.Y(low, type="quantitative", title=""),
            y2=alt.Y2(high),
        )
    )
    layers: list[alt.Chart] = [band]
    if mid:
        mid_style = resolve_series_style("actual")
        mid_line = (
            alt.Chart(df)
            .mark_line(color=mid_style["color"], strokeWidth=mid_style["strokeWidth"])
            .encode(
                x=alt.X(x, type=x_type),
                y=alt.Y(mid, type="quantitative"),
            )
        )
        layers.append(mid_line)
    chart = alt.layer(*layers)
    if title:
        chart = chart.properties(title=title)
    return chart
