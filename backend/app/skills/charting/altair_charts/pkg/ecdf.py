# backend/app/skills/altair_charts/pkg/ecdf.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.charting.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def ecdf(
    df: pd.DataFrame,
    value: str,
    group: str | None = None,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    required = [value] + ([group] if group else [])
    missing = [f for f in required if f not in df.columns]
    if missing:
        raise KeyError(
            f"ecdf(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    primary = resolve_series_style("primary")

    groupby = [group] if group else []
    window_kwargs = {
        "cumulative_count": "count()",
        "sort": [alt.SortField(field=value, order="ascending")],
    }
    if groupby:
        window_kwargs["groupby"] = groupby

    calc_expr = "datum.cumulative_count / length(data)"
    base = (
        alt.Chart(df)
        .transform_window(**window_kwargs)
        .transform_joinaggregate(total_count="count()", groupby=groupby)
        .transform_calculate(ecdf="datum.cumulative_count / datum.total_count")
    )
    if group:
        line = base.mark_line(strokeWidth=primary["strokeWidth"], interpolate="step-after").encode(
            x=alt.X(f"{value}:Q", title=value),
            y=alt.Y("ecdf:Q", title="empirical CDF"),
            color=alt.Color(group, type="nominal", title=group),
        )
    else:
        line = base.mark_line(
            strokeWidth=primary["strokeWidth"],
            interpolate="step-after",
            color=primary["color"],
        ).encode(
            x=alt.X(f"{value}:Q", title=value),
            y=alt.Y("ecdf:Q", title="empirical CDF"),
        )
    chart = line
    if title:
        chart = chart.properties(title=title)
    # eliminate unused helper var
    _ = calc_expr
    return chart
