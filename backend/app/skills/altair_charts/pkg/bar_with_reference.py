# backend/app/skills/altair_charts/pkg/bar_with_reference.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def bar_with_reference(
    df: pd.DataFrame,
    x: str,
    y: str,
    reference_value: float,
    reference_label: str | None = None,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (x, y) if f not in df.columns]
    if missing:
        raise KeyError(
            f"bar_with_reference(): missing fields {missing}; df has columns {list(df.columns)}"
        )
    bars = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(x, type="nominal", title=x),
            y=alt.Y(y, type="quantitative", title=y),
        )
    )
    ref_style = resolve_series_style("reference")
    rule_kwargs = {
        "color": ref_style["color"],
        "strokeWidth": ref_style["strokeWidth"],
        "strokeDash": ref_style.get("strokeDash", [2, 2]),
    }
    rule_df = pd.DataFrame({"_ref": [reference_value]})
    rule = alt.Chart(rule_df).mark_rule(**rule_kwargs).encode(y=alt.Y("_ref:Q"))
    layers: list[alt.Chart] = [bars, rule]
    if reference_label:
        text_df = pd.DataFrame({"_ref": [reference_value], "_label": [reference_label]})
        text = (
            alt.Chart(text_df)
            .mark_text(align="left", dx=6, dy=-4, color=ref_style["color"])
            .encode(y="_ref:Q", text="_label:N")
        )
        layers.append(text)
    chart = alt.layer(*layers)
    if title:
        chart = chart.properties(title=title)
    return chart
