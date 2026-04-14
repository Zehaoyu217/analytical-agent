from __future__ import annotations

import json
from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, pearsonr, spearmanr

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.skills.correlation.bootstrap import bootstrap_ci
from app.skills.correlation.method import detect_nonlinearity, pick_method
from app.skills.correlation.preprocess import (
    apply_detrend,
    drop_na_rows,
    partial_residuals,
)
from app.skills.correlation.result import CorrelationResult


def _p_value(method: str, x: np.ndarray, y: np.ndarray) -> float:
    if method == "pearson":
        return float(pearsonr(x, y).pvalue)
    if method == "spearman":
        return float(spearmanr(x, y).pvalue)
    if method == "kendall":
        return float(kendalltau(x, y).pvalue)
    return float("nan")


def _point_estimate(method: str, x: np.ndarray, y: np.ndarray) -> float:
    if method == "pearson":
        return float(pearsonr(x, y).statistic)
    if method == "spearman":
        return float(spearmanr(x, y).correlation)
    if method == "kendall":
        return float(kendalltau(x, y).statistic)
    if method == "distance":
        try:
            from scipy.spatial.distance import pdist, squareform
        except ImportError as e:
            raise RuntimeError(f"distance correlation requires scipy: {e}") from e
        a = squareform(pdist(x.reshape(-1, 1)))
        b = squareform(pdist(y.reshape(-1, 1)))
        a_centered = a - a.mean(axis=0) - a.mean(axis=1)[:, None] + a.mean()
        b_centered = b - b.mean(axis=0) - b.mean(axis=1)[:, None] + b.mean()
        dcov2 = float((a_centered * b_centered).mean())
        dvar_a = float((a_centered * a_centered).mean())
        dvar_b = float((b_centered * b_centered).mean())
        denom = (dvar_a * dvar_b) ** 0.5
        return 0.0 if denom == 0 else (dcov2 / denom) ** 0.5
    raise ValueError(f"unknown method: {method}")


def correlate(
    df: pd.DataFrame,
    x: str,
    y: str,
    method: str = "auto",
    partial_on: Sequence[str] | None = None,
    detrend: str | None = None,
    handle_na: str = "report",
    bootstrap_n: int = 1000,
    store: ArtifactStore | None = None,
    session_id: str | None = None,
    seed: int = 0,
) -> CorrelationResult:
    partial_cols = tuple(partial_on or ())
    required = [x, y, *partial_cols]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"correlation: column '{missing[0]}' not in DataFrame. "
            f"Available: {list(df.columns)}"
        )

    frame = df[list(required)].copy()
    if handle_na == "fail" and frame.isna().any().any():
        raise ValueError("correlation: NaN present and handle_na='fail'")
    frame, na_dropped = drop_na_rows(frame)

    if detrend is not None:
        frame[x] = apply_detrend(frame[x], detrend)
        frame[y] = apply_detrend(frame[y], detrend)
        frame = frame.dropna().reset_index(drop=True)

    if partial_cols:
        x_arr, y_arr = partial_residuals(
            frame[x].to_numpy(),
            frame[y].to_numpy(),
            frame[list(partial_cols)].to_numpy(),
        )
    else:
        x_arr = frame[x].to_numpy()
        y_arr = frame[y].to_numpy()

    n_eff = x_arr.size
    if n_eff < 10:
        raise ValueError(
            f"correlation: n_effective={n_eff} < 10 after NA handling. "
            "Increase data or set handle_na='fail'."
        )

    method_used = pick_method(x_arr, y_arr, method)
    coefficient = _point_estimate(method_used, x_arr, y_arr)
    p_value = _p_value(method_used, x_arr, y_arr)
    if method_used in {"pearson", "spearman", "kendall"}:
        ci_lo, ci_hi = bootstrap_ci(
            x_arr, y_arr, method_used, n_resamples=bootstrap_n, seed=seed
        )
    else:
        ci_lo, ci_hi = coefficient, coefficient
    nonlinear = detect_nonlinearity(x_arr, y_arr)

    artifact_id = None
    if store is not None and session_id is not None:
        payload = {
            "result": {
                "coefficient": coefficient, "ci_low": ci_lo, "ci_high": ci_hi,
                "p_value": p_value, "method_used": method_used,
                "nonlinear_warning": nonlinear, "n_effective": int(n_eff),
                "na_dropped": int(na_dropped), "x": x, "y": y,
                "partial_on": list(partial_cols), "detrend": detrend,
            },
            "sample_size": int(n_eff),
        }
        artifact = Artifact(
            type="analysis",
            content=json.dumps(payload),
            format="json",
            title=f"correlation({x},{y})",
            description=f"{method_used} r={coefficient:.3f} CI[{ci_lo:.3f},{ci_hi:.3f}] n={n_eff}",
        )
        saved = store.add_artifact(session_id, artifact)
        artifact_id = saved.id

    return CorrelationResult(
        coefficient=coefficient, ci_low=ci_lo, ci_high=ci_hi,
        p_value=p_value, method_used=method_used,
        nonlinear_warning=nonlinear, n_effective=n_eff,
        na_dropped=na_dropped, x=x, y=y,
        partial_on=partial_cols, detrend=detrend,
        bootstrap_n=bootstrap_n, artifact_id=artifact_id,
    )
