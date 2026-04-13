from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk


def run(df: pd.DataFrame, key_candidates: list[str] | None = None) -> dict[str, Any]:
    risks: list[Risk] = []
    dup_rows = int(df.duplicated().sum())
    if dup_rows > 0:
        risks.append(
            Risk(
                kind="duplicate_rows",
                severity="HIGH",
                columns=tuple(df.columns),
                detail=f"{dup_rows} full-row duplicates detected",
                mitigation="Run `df.drop_duplicates()` or investigate the source for re-ingestion bugs.",
            )
        )
    dup_key_detail: dict[str, int] = {}
    if key_candidates:
        for col in key_candidates:
            if col not in df.columns:
                continue
            dup = int(df.duplicated(subset=[col]).sum())
            dup_key_detail[col] = dup
            if dup > 0:
                risks.append(
                    Risk(
                        kind="duplicate_key",
                        severity="BLOCKER",
                        columns=(col,),
                        detail=f"'{col}' has {dup} duplicate values; not a valid primary key",
                        mitigation="Re-derive the key, deduplicate with a tie-breaker, or choose a composite key.",
                    )
                )
    return {"duplicate_rows": dup_rows, "duplicate_keys": dup_key_detail, "risks": risks}
