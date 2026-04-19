from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.skills.statistical_analysis.distribution_fit.candidates import auto_candidates
from app.skills.statistical_analysis.distribution_fit.charts import pdf_overlay_chart, qq_chart
from app.skills.statistical_analysis.distribution_fit.fit_one import SUPPORTED
from app.skills.statistical_analysis.distribution_fit.hill import hill_alpha
from app.skills.statistical_analysis.distribution_fit.rank import rank_candidates
from app.skills.statistical_analysis.distribution_fit.result import FitResult

OUTLIER_TAIL_PROB = 0.001


def _outlier_indices(arr: np.ndarray, candidate: Any, threshold: float) -> tuple[int, ...]:
    dist = SUPPORTED[candidate.name]
    sf = dist.sf(arr, *candidate.params)
    cdf = dist.cdf(arr, *candidate.params)
    mask = (sf < threshold) | (cdf < threshold)
    return tuple(int(i) for i in np.where(mask)[0])


def _save_chart_artifact(
    store: ArtifactStore, session_id: str, chart: Any, title: str, summary: str
) -> str:
    json_spec = chart.to_json()
    art = store.add_artifact(
        session_id,
        Artifact(
            type="chart",
            content=json_spec,
            format="vega-lite",
            title=title,
            description=summary,
        ),
    )
    return art.id


def fit(
    series: pd.Series | np.ndarray,
    candidates: str | list[str] = "auto",
    store: ArtifactStore | None = None,
    session_id: str | None = None,
) -> FitResult:
    arr = (
        series.dropna().to_numpy()
        if isinstance(series, pd.Series)
        else np.asarray(series, dtype=float)
    )
    arr = arr[~np.isnan(arr)]
    if arr.size < 50:
        raise ValueError(f"distribution_fit: n={arr.size} < 50")

    names = auto_candidates(arr) if candidates == "auto" else list(candidates)
    if not names:
        raise ValueError("distribution_fit: no candidates chosen.")
    ranked = rank_candidates(arr, names)
    if not ranked:
        raise RuntimeError("distribution_fit: all candidates failed to fit.")
    best = ranked[0]

    qq_id: str | None = None
    pdf_id: str | None = None
    if store is not None and session_id is not None:
        qq_id = _save_chart_artifact(
            store, session_id, qq_chart(arr, best),
            title=f"Q-Q ({best.name})",
            summary=f"Q-Q plot vs {best.name}",
        )
        pdf_id = _save_chart_artifact(
            store, session_id, pdf_overlay_chart(arr, best),
            title=f"PDF overlay ({best.name})",
            summary=f"Histogram + fitted {best.name} PDF",
        )

    outlier_ids = _outlier_indices(arr, best, threshold=OUTLIER_TAIL_PROB)
    hill = hill_alpha(arr, k_frac=0.10)

    return FitResult(
        best=best,
        ranked=tuple(ranked),
        hill_alpha=hill,
        qq_artifact_id=qq_id,
        pdf_overlay_artifact_id=pdf_id,
        outlier_threshold=OUTLIER_TAIL_PROB,
        outlier_indices=outlier_ids,
    )
