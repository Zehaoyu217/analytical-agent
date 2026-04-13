# backend/app/skills/analysis_plan/pkg/steps.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Depth = Literal["quick", "standard", "deep"]


@dataclass(frozen=True)
class StepTemplate:
    slug: str
    label: str
    skill: str            # skill to invoke for this step (or "agent" for no-skill)
    artifact_hint: str    # what artifact ID should result
    required_for: tuple[Depth, ...] = field(default=("quick", "standard", "deep"))


STEP_CATALOG: tuple[StepTemplate, ...] = (
    StepTemplate(
        slug="orient",
        label="Read wiki working + index; confirm dataset",
        skill="agent",
        artifact_hint="none (scratchpad only)",
    ),
    StepTemplate(
        slug="profile",
        label="Run data_profiler on the target dataset",
        skill="data_profiler",
        artifact_hint="profile-json + profile-html",
    ),
    StepTemplate(
        slug="hypothesize",
        label="State hypothesis and method in scratchpad COT",
        skill="agent",
        artifact_hint="none (scratchpad only)",
    ),
    StepTemplate(
        slug="analyze",
        label="Run the primary analysis (correlate / compare / characterize / fit)",
        skill="varies",
        artifact_hint="chart + table",
    ),
    StepTemplate(
        slug="deepen",
        label="Segment / partial / lagged variant; investigate anomalies",
        skill="varies",
        artifact_hint="chart + table",
        required_for=("standard", "deep"),
    ),
    StepTemplate(
        slug="segment_sensitivity",
        label="Segment-level sensitivity (partial correlation, group_compare per segment)",
        skill="varies",
        artifact_hint="table",
        required_for=("deep",),
    ),
    StepTemplate(
        slug="validate",
        label="stat_validate on every inferential claim",
        skill="stat_validate",
        artifact_hint="validation report",
    ),
    StepTemplate(
        slug="report",
        label="Build research_memo with promoted findings",
        skill="report_builder",
        artifact_hint="report-md + report-html (+ report-pdf)",
    ),
)


def pick_steps(depth: Depth) -> list[StepTemplate]:
    if depth not in ("quick", "standard", "deep"):
        raise ValueError(f"Unknown depth '{depth}'. Use quick | standard | deep.")
    return [s for s in STEP_CATALOG if depth in s.required_for]
