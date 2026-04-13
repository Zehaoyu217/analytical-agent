from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

SKEW_THRESHOLD = 3.0
NEAR_CONST_THRESHOLD = 0.95


def run(df: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, dict[str, float]] = {}
    risks: list[Risk] = []
    for col in df.columns:
        s = df[col].dropna()
        if s.empty:
            continue
        n_unique = int(s.nunique())
        if n_unique == 1:
            risks.append(
                Risk(
                    kind="constant_column",
                    severity="MEDIUM",
                    columns=(col,),
                    detail=f"column '{col}' has a single value",
                    mitigation="Consider dropping before modeling.",
                )
            )
            continue
        mode_frac = float(s.value_counts(normalize=True).iloc[0])
        if mode_frac >= NEAR_CONST_THRESHOLD:
            risks.append(
                Risk(
                    kind="near_constant",
                    severity="MEDIUM",
                    columns=(col,),
                    detail=f"{mode_frac * 100:.1f}% of '{col}' is a single mode value",
                    mitigation="Likely uninformative; validate before using as a feature.",
                )
            )
        if pd.api.types.is_numeric_dtype(s):
            skew = float(s.skew())
            stats[col] = {"skew": skew, "kurtosis": float(s.kurt())}
            if abs(skew) >= SKEW_THRESHOLD:
                risks.append(
                    Risk(
                        kind="skew_heavy",
                        severity="MEDIUM",
                        columns=(col,),
                        detail=f"'{col}' skew={skew:.2f} — consider log or rank transform",
                        mitigation=(
                            "Apply np.log1p for right-skew or a winsorized transform before "
                            "parametric tests."
                        ),
                    )
                )
    return {"stats": stats, "risks": risks}
