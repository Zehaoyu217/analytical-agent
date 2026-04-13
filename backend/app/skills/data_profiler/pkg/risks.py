# backend/app/skills/data_profiler/pkg/risks.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["BLOCKER", "HIGH", "MEDIUM", "LOW"]

RISK_KINDS: tuple[str, ...] = (
    "missing_over_threshold",
    "missing_co_occurrence",
    "duplicate_rows",
    "duplicate_key",
    "constant_column",
    "near_constant",
    "high_cardinality_categorical",
    "low_cardinality_numeric",
    "mixed_types",
    "date_gaps",
    "date_non_monotonic",
    "date_future",
    "outliers_extreme",
    "skew_heavy",
    "suspicious_zeros",
    "suspicious_placeholders",
    "unit_inconsistency",
    "suspected_foreign_key",
    "collinear_pair",
    "class_imbalance",
    "timezone_naive",
)

SEVERITY_ORDER: dict[str, int] = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass(frozen=True)
class Risk:
    kind: str
    severity: Severity
    columns: tuple[str, ...]
    detail: str
    mitigation: str

    def __post_init__(self) -> None:
        if self.kind not in RISK_KINDS:
            raise ValueError(f"unknown risk kind: {self.kind}")

    def sort_key(self) -> tuple[int, str, tuple[str, ...]]:
        return (SEVERITY_ORDER[self.severity], self.kind, self.columns)
