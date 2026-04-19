from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.skills.statistical_analysis.time_series.characterize import characterize


@dataclass(frozen=True, slots=True)
class LagCorrelationResult:
    lags: np.ndarray
    coefficients: np.ndarray
    significant_lags: list[int]


def _shift(arr: np.ndarray, lag: int) -> np.ndarray:
    if lag == 0:
        return arr.copy()
    if lag > 0:
        return np.concatenate([np.full(lag, np.nan), arr[:-lag]])
    return np.concatenate([arr[-lag:], np.full(-lag, np.nan)])


def lag_correlate(
    x: pd.Series | np.ndarray,
    y: pd.Series | np.ndarray,
    max_lag: int = 30,
    accept_non_stationary: bool = False,
) -> LagCorrelationResult:
    x_arr = x.dropna().to_numpy() if isinstance(x, pd.Series) else np.asarray(x, dtype=float)
    y_arr = y.dropna().to_numpy() if isinstance(y, pd.Series) else np.asarray(y, dtype=float)
    n = min(x_arr.size, y_arr.size)
    x_arr = x_arr[:n]
    y_arr = y_arr[:n]

    if not accept_non_stationary and (
        not characterize(x_arr).stationary or not characterize(y_arr).stationary
    ):
        raise ValueError(
            "time_series.lag_correlate: inputs are non_stationary. "
            "Set accept_non_stationary=True to override, or difference inputs first."
        )

    lags = np.arange(-max_lag, max_lag + 1)
    coefs = np.empty(lags.size)
    for i, lag in enumerate(lags):
        shifted = _shift(y_arr, int(lag))
        mask = ~np.isnan(shifted)
        if mask.sum() < 10:
            coefs[i] = np.nan
            continue
        coefs[i] = float(np.corrcoef(x_arr[mask], shifted[mask])[0, 1])
    threshold = 2.0 / np.sqrt(n)
    significant = [
        int(lag)
        for lag, c in zip(lags, coefs, strict=False)
        if not np.isnan(c) and abs(c) > threshold
    ]
    return LagCorrelationResult(lags=lags, coefficients=coefs, significant_lags=significant)
