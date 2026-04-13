# backend/app/skills/data_profiler/pkg/sections/schema.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk


def run(df: pd.DataFrame) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    risks: list[Risk] = []
    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        null_count = int(series.isna().sum())
        columns.append(
            {
                "name": col,
                "dtype": dtype,
                "null_count": null_count,
                "non_null_count": int(len(series) - null_count),
            }
        )
        if pd.api.types.is_object_dtype(series):
            non_null = series.dropna()
            types = {type(v).__name__ for v in non_null}
            if len(types) > 1:
                risks.append(
                    Risk(
                        kind="mixed_types",
                        severity="HIGH",
                        columns=(col,),
                        detail=f"column '{col}' contains mixed types: {sorted(types)}",
                        mitigation=(
                            "Coerce to a single type before analysis "
                            "(pd.to_numeric(errors='coerce') or str())."
                        ),
                    )
                )
    return {"n_rows": int(len(df)), "n_cols": int(len(df.columns)), "columns": columns, "risks": risks}
