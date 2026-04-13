# backend/app/skills/altair_charts/pkg/violin.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def violin(
    df: pd.DataFrame,
    value: str,
    group: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (value, group) if f not in df.columns]
    if missing:
        raise KeyError(
            f"violin(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    primary = resolve_series_style("primary")
    base = (
        alt.Chart(df)
        .transform_density(
            density=value,
            as_=[value, "density"],
            groupby=[group],
        )
        .mark_area(
            orient="horizontal",
            color=primary["color"],
            opacity=0.8,
        )
        .encode(
            y=alt.Y(f"{value}:Q", title=value),
            x=alt.X(
                "density:Q",
                stack="center",
                impute=None,
                title=None,
                axis=alt.Axis(labels=False, grid=False, ticks=False, title=None),
            ),
        )
        .properties(width=120, height=300)
    )
    chart = base.facet(
        column=alt.Column(group, type="nominal", header=alt.Header(titleOrient="bottom", labelOrient="bottom")),
    )
    if title:
        chart = chart.properties(title=title)
    return chart
