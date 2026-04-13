from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

HIGH_CARD_RATIO = 0.9


def run(df: pd.DataFrame, key_candidates: list[str] | None = None) -> dict[str, Any]:
    risks: list[Risk] = []
    cardinalities: dict[str, int] = {}
    n = len(df)
    for col in df.columns:
        s = df[col].dropna()
        u = int(s.nunique())
        cardinalities[col] = u
        is_categorical_like = (
            pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s)
        ) and not pd.api.types.is_numeric_dtype(s)
        if is_categorical_like and n and u / max(n, 1) >= HIGH_CARD_RATIO:
            risks.append(
                Risk(
                    kind="high_cardinality_categorical",
                    severity="LOW",
                    columns=(col,),
                    detail=f"'{col}' has {u} unique values out of {n} rows",
                    mitigation=(
                        "Avoid one-hot encoding directly; consider target encoding or dropping."
                    ),
                )
            )
        if pd.api.types.is_numeric_dtype(s) and u < 10 and n > 100:
            risks.append(
                Risk(
                    kind="low_cardinality_numeric",
                    severity="LOW",
                    columns=(col,),
                    detail=f"numeric column '{col}' only has {u} distinct values",
                    mitigation=(
                        "Consider treating as categorical; arithmetic may not be meaningful."
                    ),
                )
            )
    if key_candidates:
        for col in df.columns:
            if col in key_candidates:
                continue
            s = df[col].dropna()
            if not pd.api.types.is_integer_dtype(s):
                continue
            if s.nunique() > 1 and s.nunique() <= n:
                risks.append(
                    Risk(
                        kind="suspected_foreign_key",
                        severity="LOW",
                        columns=(col,),
                        detail=f"'{col}' looks like a foreign key (integer, many distinct values)",
                        mitigation=f"Confirm join target among candidates {key_candidates}.",
                    )
                )
    return {"cardinalities": cardinalities, "risks": risks}
