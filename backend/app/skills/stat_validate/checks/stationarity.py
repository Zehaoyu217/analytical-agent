from __future__ import annotations

import numpy as np
from statsmodels.tsa.stattools import adfuller

from app.skills.stat_validate.verdict import Violation


def _is_non_stationary(series: np.ndarray) -> bool:
    if series.size < 20 or np.std(series) == 0:
        return False
    try:
        p = float(adfuller(series, autolag="AIC")[1])
    except Exception:
        return False
    return p > 0.05


def check_stationarity_for_spurious(
    payload: dict,
    x_series: np.ndarray | None,
    y_series: np.ndarray | None,
) -> Violation | None:
    if x_series is None or y_series is None:
        return None
    if payload.get("detrend") is not None:
        return None
    if _is_non_stationary(x_series) and _is_non_stationary(y_series):
        return Violation(
            code="spurious_correlation_risk",
            severity="WARN",
            message="both inputs non-stationary (ADF p>0.05) with no detrending",
            gotcha_refs=("non_stationarity", "spurious_correlation"),
        )
    return None
