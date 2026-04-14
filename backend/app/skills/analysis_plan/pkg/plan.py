# backend/app/skills/analysis_plan/pkg/plan.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.skills.analysis_plan.pkg.steps import StepTemplate, pick_steps

Depth = Literal["quick", "standard", "deep"]

WIKI_DIR = Path("wiki")  # resolved relative to project root; overridden in tests.


@dataclass(frozen=True)
class PlanStep:
    idx: int
    slug: str
    label: str
    skill: str
    artifact_hint: str

    @classmethod
    def from_template(cls, idx: int, tpl: StepTemplate) -> PlanStep:
        return cls(idx=idx, slug=tpl.slug, label=tpl.label, skill=tpl.skill, artifact_hint=tpl.artifact_hint)


@dataclass(frozen=True)
class PlanResult:
    question: str
    dataset: str | None
    depth: Depth
    steps: tuple[PlanStep, ...]
    working_md_path: Path


def plan(
    question: str,
    dataset: str | None = None,
    depth: Depth = "standard",
) -> PlanResult:
    q = question.strip()
    if not q:
        raise ValueError("EMPTY_QUESTION: plan() requires a non-empty question.")
    templates = pick_steps(depth)
    steps = tuple(PlanStep.from_template(i + 1, t) for i, t in enumerate(templates))

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    working_path = WIKI_DIR / "working.md"
    working_path.write_text(_render_working_md(q, dataset, depth, steps), encoding="utf-8")

    return PlanResult(question=q, dataset=dataset, depth=depth, steps=steps, working_md_path=working_path)


def _render_working_md(
    question: str,
    dataset: str | None,
    depth: Depth,
    steps: tuple[PlanStep, ...],
) -> str:
    lines: list[str] = []
    lines.append(f"# Working — {question}")
    lines.append("")
    lines.append(f"- **Depth:** {depth}")
    lines.append(f"- **Dataset:** {dataset or '(not set)'}")
    lines.append("")
    lines.append("## TODO")
    lines.append("")
    for s in steps:
        lines.append(f"- [ ] {s.idx}. **{s.slug}** — {s.label} → _{s.artifact_hint}_")
    lines.append("")
    lines.append("## COT")
    lines.append("")
    lines.append("_(append-only chain of thought)_")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.append("_(promoted findings land here with `[F-<date>-<nnn>]`)_")
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    lines.append("_(artifact IDs cited by findings)_")
    lines.append("")
    return "\n".join(lines)
