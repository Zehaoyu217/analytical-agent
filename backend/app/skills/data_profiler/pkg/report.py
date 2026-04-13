# backend/app/skills/data_profiler/pkg/report.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.skills.data_profiler.pkg.risks import Risk


@dataclass(frozen=True)
class ProfileReport:
    name: str
    n_rows: int
    n_cols: int
    summary: str
    risks: list[Risk] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)
    artifact_id: str | None = None
    report_artifact_id: str | None = None
