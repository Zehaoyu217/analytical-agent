"""Eval runner — evaluates agent traces against rubric configurations."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.evals.grading import grade_level
from app.evals.types import AgentTrace, DimensionGrade, EvalResult, LevelResult

if TYPE_CHECKING:
    from app.evals.judge import LLMJudge
    from app.evals.rubric import DimensionRubric, RubricConfig

DeterministicCheck = Callable[[AgentTrace], bool]


def grade_deterministic(
    name: str,
    rubric: DimensionRubric,
    trace: AgentTrace,
    checks: list[DeterministicCheck],
) -> DimensionGrade:
    """Grade a purely deterministic dimension by check pass ratio."""
    if not checks:
        return DimensionGrade(
            name=name,
            grade="C",
            score=0.4,
            weight=rubric.weight,
            justification="No deterministic checks defined — default C",
        )
    passed = sum(1 for check in checks if check(trace))
    ratio = passed / len(checks)
    if ratio >= 0.9:
        grade_str, score = "A", 1.0
    elif ratio >= 0.6:
        grade_str, score = "B", 0.7
    elif ratio >= 0.3:
        grade_str, score = "C", 0.4
    else:
        grade_str, score = "F", 0.0
    return DimensionGrade(
        name=name,
        grade=grade_str,
        score=score,
        weight=rubric.weight,
        justification=f"Passed {passed}/{len(checks)} deterministic checks",
    )


async def evaluate_level(
    rubric: RubricConfig,
    trace: AgentTrace,
    judge: LLMJudge,
    deterministic_checks: dict[str, list[DeterministicCheck]] | None = None,
) -> LevelResult:
    """Run a full level evaluation against an agent trace.

    For 'llm_judge' dimensions: delegates to the LLM judge.
    For 'deterministic' dimensions: uses check functions (pass ratio → grade).
    For 'hybrid' dimensions: deterministic checks must all pass; then LLM grades.
      If deterministic checks fail → F.
    """
    checks = deterministic_checks or {}
    dimensions: list[DimensionGrade] = []

    for dim_name, dim_rubric in rubric.dimensions.items():
        if dim_rubric.type == "llm_judge":
            grade = await judge.grade_dimension(dim_name, dim_rubric, trace)
        elif dim_rubric.type == "deterministic":
            grade = grade_deterministic(
                dim_name, dim_rubric, trace, checks.get(dim_name, []),
            )
        else:  # hybrid
            dim_checks = checks.get(dim_name, [])
            all_pass = all(check(trace) for check in dim_checks) if dim_checks else True
            if not all_pass:
                grade = DimensionGrade(
                    name=dim_name,
                    grade="F",
                    score=0.0,
                    weight=dim_rubric.weight,
                    justification="Failed deterministic checks",
                )
            else:
                grade = await judge.grade_dimension(dim_name, dim_rubric, trace)
        dimensions.append(grade)

    return grade_level(rubric.level, rubric.name, dimensions)


def format_level_result(result: LevelResult) -> str:
    """Format a single level result for console output."""
    dims = "  ".join(f"{d.name}:{d.grade}" for d in result.dimensions)
    return (
        f"Level {result.level} — {result.name}:"
        f"{result.grade:>6}  ({dims})"
    )


def format_eval_result(result: EvalResult) -> str:
    """Format the full eval result for console output."""
    lines = [format_level_result(lev) for lev in result.levels]
    lines.append(f"Overall:{result.overall_grade:>25}")
    return "\n".join(lines)
