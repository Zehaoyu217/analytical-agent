# backend/app/skills/data_profiler/pkg/sections/missingness.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

BLOCKER_THRESHOLD = 0.5
HIGH_THRESHOLD = 0.2
CO_OCCURRENCE_THRESHOLD = 0.8


def run(df: pd.DataFrame) -> dict[str, Any]:
    n = len(df)
    risks: list[Risk] = []
    per_col: dict[str, float] = {}
    for col in df.columns:
        frac = float(df[col].isna().mean()) if n else 0.0
        per_col[col] = frac
        if frac >= BLOCKER_THRESHOLD:
            risks.append(
                Risk(
                    kind="missing_over_threshold",
                    severity="BLOCKER",
                    columns=(col,),
                    detail=f"{frac * 100:.1f}% of '{col}' is null",
                    mitigation="Drop the column or impute before analysis; do not silently ignore.",
                )
            )
        elif frac >= HIGH_THRESHOLD:
            risks.append(
                Risk(
                    kind="missing_over_threshold",
                    severity="HIGH",
                    columns=(col,),
                    detail=f"{frac * 100:.1f}% of '{col}' is null",
                    mitigation="Either impute with a defensible strategy or restrict analysis to non-null rows and disclose.",
                )
            )

    # Co-occurrence: look for pairs that are null together
    nan_mask = df.isna()
    cols_with_nulls = [c for c in df.columns if per_col[c] > 0]
    for i, a in enumerate(cols_with_nulls):
        for b in cols_with_nulls[i + 1 :]:
            a_null = nan_mask[a]
            b_null = nan_mask[b]
            joint = int((a_null & b_null).sum())
            base = int(a_null.sum())
            if base and joint / base >= CO_OCCURRENCE_THRESHOLD:
                risks.append(
                    Risk(
                        kind="missing_co_occurrence",
                        severity="MEDIUM",
                        columns=(a, b),
                        detail=f"when '{a}' is null, '{b}' is null {joint / base * 100:.0f}% of the time",
                        mitigation="Treat these as a single 'not collected' case; consider one indicator column.",
                    )
                )
    return {"per_column_fraction": per_col, "risks": risks}
