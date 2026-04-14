from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from app.skills.stat_validate.verdict import Violation

SHRINK_RATIO = 0.5


def check_simpsons_paradox(
    payload: dict,
    frame: pd.DataFrame | None,
    stratify_candidates: Sequence[str],
) -> Violation | None:
    if frame is None or not stratify_candidates:
        return None
    x_col = payload.get("x")
    y_col = payload.get("y")
    pooled = payload.get("coefficient")
    if x_col is None or y_col is None or pooled is None:
        return None
    for stratum_col in stratify_candidates:
        if stratum_col not in frame.columns:
            continue
        per_stratum: list[float] = []
        for _, sub in frame.dropna(subset=[x_col, y_col, stratum_col]).groupby(stratum_col):
            if len(sub) < 10:
                continue
            if sub[x_col].std() == 0 or sub[y_col].std() == 0:
                continue
            per_stratum.append(float(np.corrcoef(sub[x_col], sub[y_col])[0, 1]))
        if not per_stratum:
            continue
        avg_stratified = float(np.mean(per_stratum))
        if pooled * avg_stratified < 0:
            return Violation(
                code="simpsons_flip",
                severity="FAIL",
                message=(
                    f"pooled r={pooled:.3f} flips sign vs. mean stratum "
                    f"r={avg_stratified:.3f} stratified by '{stratum_col}'"
                ),
                gotcha_refs=("simpsons_paradox",),
            )
        if abs(avg_stratified) < abs(pooled) * SHRINK_RATIO:
            return Violation(
                code="simpsons_shrink",
                severity="WARN",
                message=(
                    f"pooled r={pooled:.3f} shrinks to mean stratum "
                    f"r={avg_stratified:.3f} stratified by '{stratum_col}'"
                ),
                gotcha_refs=("simpsons_paradox",),
            )
    return None
