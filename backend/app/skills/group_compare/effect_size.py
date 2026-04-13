from __future__ import annotations

import numpy as np


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = a.size, b.size
    if n1 < 2 or n2 < 2:
        return float("nan")
    mean_diff = a.mean() - b.mean()
    pooled_var = ((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2)
    if pooled_var <= 0:
        return 0.0
    return float(abs(mean_diff) / np.sqrt(pooled_var))


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Cliff's delta: probability a > b minus probability a < b."""
    n1, n2 = a.size, b.size
    if n1 == 0 or n2 == 0:
        return float("nan")
    greater = np.sum(a[:, None] > b[None, :])
    less = np.sum(a[:, None] < b[None, :])
    return float((greater - less) / (n1 * n2))


def eta_squared(groups: list[np.ndarray]) -> float:
    all_values = np.concatenate(groups)
    grand_mean = all_values.mean()
    ss_between = sum(g.size * (g.mean() - grand_mean) ** 2 for g in groups)
    ss_total = float(((all_values - grand_mean) ** 2).sum())
    if ss_total == 0:
        return 0.0
    return float(ss_between / ss_total)
