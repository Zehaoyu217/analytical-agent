from __future__ import annotations

import numpy as np
from scipy.stats import kendalltau, pearsonr, spearmanr


def _statistic(method: str, x: np.ndarray, y: np.ndarray) -> float:
    if method == "pearson":
        return float(pearsonr(x, y).statistic)
    if method == "spearman":
        return float(spearmanr(x, y).correlation)
    if method == "kendall":
        return float(kendalltau(x, y).statistic)
    raise ValueError(f"bootstrap method '{method}' not supported")


def bootstrap_ci(
    x: np.ndarray,
    y: np.ndarray,
    method: str,
    n_resamples: int,
    seed: int,
    alpha: float = 0.05,
) -> tuple[float, float]:
    n = x.size
    if n < 10:
        raise ValueError(f"bootstrap: n={n} < 10")
    if np.std(x) == 0 or np.std(y) == 0:
        raise ValueError("bootstrap: one input has zero variance")
    rng = np.random.default_rng(seed)
    stats = np.empty(n_resamples, dtype=float)
    indices = np.arange(n)
    for i in range(n_resamples):
        sample = rng.choice(indices, size=n, replace=True)
        stats[i] = _statistic(method, x[sample], y[sample])
    lo = float(np.quantile(stats, alpha / 2))
    hi = float(np.quantile(stats, 1 - alpha / 2))
    return lo, hi
