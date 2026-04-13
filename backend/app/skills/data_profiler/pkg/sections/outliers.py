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
        extreme_hi = (
            int((s > high * 10).sum()) if high > 0 else int((s > high + abs(high) * 9).sum())
        )
        extreme_lo = int((s < low * 10).sum()) if low < 0 else 0
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
