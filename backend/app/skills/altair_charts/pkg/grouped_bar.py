# backend/app/skills/altair_charts/pkg/grouped_bar.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import ensure_theme_registered


def grouped_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    category: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (x, y, category) if f not in df.columns]
    if missing:
        raise KeyError(
            f"grouped_bar(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(x, type="nominal", title=x),
            xOffset=alt.XOffset(category, type="nominal"),
            y=alt.Y(y, type="quantitative", title=y),
            color=alt.Color(category, type="nominal", title=category),
        )
    )
    if title:
        chart = chart.properties(title=title)
    return chart
