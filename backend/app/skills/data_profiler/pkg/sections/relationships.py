from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

COLLINEAR_THRESHOLD = 0.95


def run(df: pd.DataFrame) -> dict[str, Any]:
    num = df.select_dtypes(include="number")
    if num.shape[1] < 2:
        return {"correlations": [], "risks": []}
    corr = num.corr(numeric_only=True)
    pairs: list[tuple[str, str, float]] = []
    cols = list(corr.columns)
    risks: list[Risk] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            val = float(corr.loc[a, b])
            if pd.notna(val):
                pairs.append((a, b, val))
                if abs(val) >= COLLINEAR_THRESHOLD:
                    risks.append(
                        Risk(
                            kind="collinear_pair",
                            severity="MEDIUM",
                            columns=(a, b),
                            detail=f"corr({a}, {b}) = {val:.3f}",
                            mitigation="Drop one before modeling to avoid unstable coefficients.",
                        )
                    )
    return {"correlations": pairs, "risks": risks}
