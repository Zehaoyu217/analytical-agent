from __future__ import annotations

import numpy as np
import pandas as pd
import altair as alt

from app.skills.distribution_fit.fit_one import SUPPORTED, FitCandidate


def qq_chart(arr: np.ndarray, candidate: FitCandidate, variant: str = "light") -> alt.LayerChart:
    dist = SUPPORTED[candidate.name]
    x_sorted = np.sort(arr)
    n = x_sorted.size
    probs = (np.arange(1, n + 1) - 0.5) / n
    theoretical = dist.ppf(probs, *candidate.params)
    df = pd.DataFrame({"theoretical": theoretical, "observed": x_sorted})
    points = alt.Chart(df).mark_circle(size=40).encode(
        x=alt.X("theoretical:Q", title="Theoretical quantiles"),
        y=alt.Y("observed:Q", title="Observed quantiles"),
    )
    lo = float(min(df["theoretical"].min(), df["observed"].min()))
    hi = float(max(df["theoretical"].max(), df["observed"].max()))
    line_df = pd.DataFrame({"x": [lo, hi], "y": [lo, hi]})
    ref = alt.Chart(line_df).mark_line(strokeDash=[4, 4]).encode(x="x:Q", y="y:Q")
    return (points + ref).properties(
        title={
            "text": f"Q-Q vs {candidate.name}",
            "subtitle": f"params={tuple(round(p, 3) for p in candidate.params)}",
        }
    )


def pdf_overlay_chart(arr: np.ndarray, candidate: FitCandidate, variant: str = "light") -> alt.LayerChart:
    dist = SUPPORTED[candidate.name]
    lo, hi = float(np.min(arr)), float(np.max(arr))
    xs = np.linspace(lo, hi, 300)
    pdf = dist.pdf(xs, *candidate.params)
    obs = pd.DataFrame({"value": arr})
    curve = pd.DataFrame({"x": xs, "pdf": pdf})
    hist = alt.Chart(obs).mark_bar(opacity=0.4).encode(
        x=alt.X("value:Q", bin=alt.Bin(maxbins=40)),
        y=alt.Y("count()", title="density", stack=None),
    )
    line = alt.Chart(curve).mark_line().encode(
        x="x:Q", y=alt.Y("pdf:Q", axis=None),
    )
    return alt.layer(hist, line).properties(
        title={"text": f"PDF overlay — {candidate.name}"}
    )
