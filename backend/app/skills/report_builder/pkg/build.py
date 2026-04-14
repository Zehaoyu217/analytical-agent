# backend/app/skills/report_builder/pkg/build.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Template = Literal["research_memo", "analysis_brief", "full_report"]
Verdict = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True)
class Finding:
    id: str                         # e.g. F-20260412-001
    title: str
    claim: str
    evidence_ids: tuple[str, ...]
    validated_by: str               # stat_validate artifact id
    verdict: Verdict


@dataclass(frozen=True)
class FindingSection:
    finding: Finding
    body: str                       # markdown
    chart_id: str | None = None
    table_id: str | None = None
    caveats: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Methodology:
    method: str
    data_sources: tuple[str, ...]
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class ReportSpec:
    title: str
    author: str
    summary: str
    key_points: tuple[str, ...]
    findings: tuple[FindingSection, ...]
    methodology: Methodology
    caveats: tuple[str, ...]
    appendix: tuple[str, ...]
    theme_variant: str = "editorial"
    subtitle: str | None = None


@dataclass(frozen=True)
class ReportResult:
    template: Template
    formats: tuple[str, ...]
    paths: dict[str, Path]          # format → absolute path
    artifact_ids: dict[str, str]    # format → artifact id


_REQUIRED_KP = {"research_memo": 3, "analysis_brief": 3, "full_report": 3}


def validate_spec(spec: ReportSpec, template: Template) -> None:
    if template not in _REQUIRED_KP:
        raise ValueError(
            f"UNKNOWN_TEMPLATE: Unknown template '{template}'. "
            f"Use research_memo | analysis_brief | full_report."
        )
    n = _REQUIRED_KP[template]
    if len(spec.key_points) != n:
        raise ValueError(
            f"WRONG_KEY_POINT_COUNT: {template} requires exactly {n} key points, got {len(spec.key_points)}."
        )
    if not spec.methodology.method.strip() or not spec.methodology.data_sources:
        raise ValueError("MISSING_METHODOLOGY: Methodology section is required.")
    if not spec.caveats:
        raise ValueError("MISSING_METHODOLOGY: Caveats must not be empty.")
    for fs in spec.findings:
        if fs.finding.verdict == "FAIL":
            raise ValueError(
                f"FAILED_FINDING: Finding {fs.finding.id} has stat_validate verdict FAIL; cannot include."
            )
        if not fs.finding.evidence_ids:
            raise ValueError(
                f"FAILED_FINDING: Finding {fs.finding.id} has no evidence_ids."
            )
