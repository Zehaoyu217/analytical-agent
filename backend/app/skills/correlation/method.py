from __future__ import annotations

import numpy as np
from scipy.stats import pearsonr, spearmanr

VALID_METHODS = frozenset({"auto", "pearson", "spearman", "kendall", "distance"})
NONLINEAR_THRESHOLD = 0.10


def detect_nonlinearity(x: np.ndarray, y: np.ndarray) -> bool:
    if x.size < 10 or y.size < 10:
        return False
    r_pearson = float(pearsonr(x, y).statistic)
    r_spearman = float(spearmanr(x, y).correlation)
    return abs(r_spearman) - abs(r_pearson) > NONLINEAR_THRESHOLD


def pick_method(x: np.ndarray, y: np.ndarray, requested: str) -> str:
    if requested not in VALID_METHODS:
        raise ValueError(f"unknown method: {requested}")
    if requested != "auto":
        return requested
    return "spearman" if detect_nonlinearity(x, y) else "pearson"
