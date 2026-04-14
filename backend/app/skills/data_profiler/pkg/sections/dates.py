from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk


def _is_date(series: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(series)


def run(df: pd.DataFrame) -> dict[str, Any]:
    risks: list[Risk] = []
    now = datetime.now(UTC)
    for col in df.columns:
        if not _is_date(df[col]):
            continue
        s = df[col].dropna()
        if s.empty:
            continue
        if s.dt.tz is None:
            risks.append(
                Risk(
                    kind="timezone_naive",
                    severity="LOW",
                    columns=(col,),
                    detail=f"'{col}' is timezone-naive",
                    mitigation=(
                        "Use `tz_localize` to fix the origin zone before comparing across sources."
                    ),
                )
            )
        if not s.sort_values().equals(s):
            risks.append(
                Risk(
                    kind="date_non_monotonic",
                    severity="LOW",
                    columns=(col,),
                    detail=f"'{col}' is not monotonically ordered",
                    mitigation="Sort before any time-series analysis.",
                )
            )
        diffs = s.sort_values().diff().dropna()
        if not diffs.empty:
            median = diffs.median()
            max_gap = diffs.max()
            if median.total_seconds() > 0 and max_gap.total_seconds() > median.total_seconds() * 5:
                risks.append(
                    Risk(
                        kind="date_gaps",
                        severity="MEDIUM",
                        columns=(col,),
                        detail=f"'{col}' has a max gap of {max_gap} vs median {median}",
                        mitigation=(
                            "Confirm the gap is real (no data) vs a reporting cadence change; "
                            "reindex if needed."
                        ),
                    )
                )
        as_utc = s if s.dt.tz is not None else s.dt.tz_localize("UTC")
        if (as_utc > now).any():
            risks.append(
                Risk(
                    kind="date_future",
                    severity="HIGH",
                    columns=(col,),
                    detail=f"'{col}' contains dates in the future",
                    mitigation=(
                        "Verify the source; future timestamps often indicate bad joins or TZ bugs."
                    ),
                )
            )
    return {"risks": risks}
