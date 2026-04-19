from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import stats

SUPPORTED = {
    "norm": stats.norm,
    "t": stats.t,
    "laplace": stats.laplace,
    "lognorm": stats.lognorm,
    "gamma": stats.gamma,
    "weibull_min": stats.weibull_min,
    "pareto": stats.pareto,
    "beta": stats.beta,
    "uniform": stats.uniform,
}


@dataclass(frozen=True, slots=True)
class FitCandidate:
    name: str
    params: tuple[float, ...]
    aic: float
    bic: float
    ks_p: float
    ad_stat: float
    log_likelihood: float


def _log_likelihood(dist: Any, params: tuple[float, ...], x: np.ndarray) -> float:
    try:
        return float(np.sum(dist.logpdf(x, *params)))
    except Exception:
        return -np.inf


def fit_one(name: str, arr: np.ndarray) -> FitCandidate:
    if name not in SUPPORTED:
        raise ValueError(f"distribution_fit: candidate '{name}' unknown.")
    dist = SUPPORTED[name]
    x = np.asarray(arr, dtype=float)
    x = x[~np.isnan(x)]
    params = dist.fit(x)
    k = len(params)
    n = x.size
    ll = _log_likelihood(dist, params, x)
    aic = 2 * k - 2 * ll
    bic = k * np.log(n) - 2 * ll
    try:
        ks_p = float(stats.kstest(x, lambda v: dist.cdf(v, *params)).pvalue)
    except Exception:
        ks_p = float("nan")
    try:
        ad_stat = (
            float(stats.anderson(x, dist="norm").statistic)
            if name == "norm"
            else float("nan")
        )
    except Exception:
        ad_stat = float("nan")
    return FitCandidate(
        name=name, params=tuple(float(p) for p in params),
        aic=float(aic), bic=float(bic),
        ks_p=ks_p, ad_stat=ad_stat, log_likelihood=float(ll),
    )
