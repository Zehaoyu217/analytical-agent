# backend/app/skills/altair_charts/pkg/stacked_bar.py
from __future__ import annotations

from typing import Literal

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import ensure_theme_registered

StackMode = Literal["absolute", "percent"]


def stacked_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    category: str,
    mode: StackMode = "absolute",
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (x, y, category) if f not in df.columns]
    if missing:
        raise KeyError(
            f"stacked_bar(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    stack = "normalize" if mode == "percent" else "zero"
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(x, type="nominal", title=x),
            y=alt.Y(y, type="quantitative", stack=stack, title=y),
            color=alt.Color(category, type="nominal", title=category),
        )
    )
    if title:
        chart = chart.properties(title=title)
    return chart
