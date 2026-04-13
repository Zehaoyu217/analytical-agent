from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

TAIL_P = 0.001
MIN_SAMPLES = 50


def run(df: pd.DataFrame) -> dict[str, Any]:
    risks: list[Risk] = []
    details: dict[str, dict[str, float]] = {}
    for col in df.columns:
        s = df[col].dropna()
        if not pd.api.types.is_numeric_dtype(s) or len(s) < MIN_SAMPLES:
            continue
        low = s.quantile(TAIL_P)
        high = s.quantile(1 - TAIL_P)
        median = s.median()
        dist_hi = max(float(high - median), 0.0)
        dist_lo = max(float(median - low), 0.0)
        extreme_hi = int((s > median + 10 * dist_hi).sum()) if dist_hi > 0 else 0
        extreme_lo = int((s < median - 10 * dist_lo).sum()) if dist_lo > 0 else 0
        details[col] = {"p001": float(low), "p999": float(high)}
        if extreme_hi + extreme_lo > 0:
            risks.append(
                Risk(
                    kind="outliers_extreme",
                    severity="MEDIUM",
                    columns=(col,),
                    detail=(
                        f"'{col}' has {extreme_hi + extreme_lo} points >10× the 0.1%/99.9% tail"
                    ),
                    mitigation=(
                        "Verify unit consistency and data-entry bugs; "
                        "winsorize before parametric tests."
                    ),
                )
            )
    return {"details": details, "risks": risks}
