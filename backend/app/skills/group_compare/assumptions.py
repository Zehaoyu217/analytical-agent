from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import anderson, levene, shapiro


def _is_normal(sample: np.ndarray, alpha: float = 0.01) -> bool:
    if sample.size < 3:
        return False
    if sample.size <= 5000:
        return float(shapiro(sample).pvalue) > alpha
    result = anderson(sample, dist="norm")
    crit = result.critical_values[2]  # 5% level
    return float(result.statistic) < crit


@dataclass(frozen=True, slots=True)
class AssumptionReport:
    k: int
    n_per_group: tuple[int, ...]
    all_normal: bool
    normal_per_group: tuple[bool, ...]
    homoscedastic: bool
    levene_p: float

    def to_dict(self) -> dict:
        return {
            "k": self.k,
            "n_per_group": list(self.n_per_group),
            "all_normal": self.all_normal,
            "normal_per_group": list(self.normal_per_group),
            "homoscedastic": self.homoscedastic,
            "levene_p": self.levene_p,
        }


def check_assumptions(groups: list[np.ndarray]) -> AssumptionReport:
    normal = tuple(_is_normal(g) for g in groups)
    if len(groups) >= 2 and all(g.size >= 3 for g in groups):
        levene_p = float(levene(*groups, center="median").pvalue)
    else:
        levene_p = float("nan")
    return AssumptionReport(
        k=len(groups),
        n_per_group=tuple(int(g.size) for g in groups),
        all_normal=all(normal),
        normal_per_group=normal,
        homoscedastic=levene_p > 0.05 if not np.isnan(levene_p) else True,
        levene_p=levene_p,
    )
