from __future__ import annotations

import pytest

from app.evals.rubric import DimensionRubric, RubricConfig
from app.evals.runner import (
    evaluate_level,
    format_eval_result,
    format_level_result,
    grade_deterministic,
)
from app.evals.types import AgentTrace, DimensionGrade, EvalResult, LevelResult


def _make_trace(output: str = "test output") -> AgentTrace:
    return AgentTrace(
        queries=["SELECT 1"],
        intermediate=[],
        final_output=output,
        token_count=100,
        duration_ms=500,
        errors=[],
    )


def _make_rubric(dim_type: str = "llm_judge") -> RubricConfig:
    return RubricConfig(
        level=1,
        name="Test Level",
        prompt="Test prompt",
        prompt_sequence=[],
        dimensions={
            "quality": DimensionRubric(
                weight=1.0,
                type=dim_type,
                criteria={"A": "Great", "B": "Good", "C": "OK"},
            ),
        },
        grading_thresholds={"A": 0.85, "B": 0.60, "C": 0.40},
    )


def test_grade_deterministic_all_pass() -> None:
    trace = _make_trace("hello world")
    checks = [lambda t: "hello" in t.final_output, lambda t: "world" in t.final_output]
    result = grade_deterministic("dim", DimensionRubric(
        weight=0.5, type="deterministic", criteria={"A": "", "B": "", "C": ""},
    ), trace, checks)
    assert result.grade == "A"
    assert result.score == 1.0


def test_grade_deterministic_partial_pass() -> None:
    trace = _make_trace("hello")
    checks = [
        lambda t: "hello" in t.final_output,
        lambda t: "world" in t.final_output,
        lambda t: "foo" in t.final_output,
    ]
    result = grade_deterministic("dim", DimensionRubric(
        weight=0.5, type="deterministic", criteria={"A": "", "B": "", "C": ""},
    ), trace, checks)
    assert result.grade == "C"  # 1/3 = 0.33


def test_grade_deterministic_none_pass() -> None:
    trace = _make_trace("nothing matches")
    checks = [lambda t: "xyz" in t.final_output]
    result = grade_deterministic("dim", DimensionRubric(
        weight=0.5, type="deterministic", criteria={"A": "", "B": "", "C": ""},
    ), trace, checks)
    assert result.grade == "F"


def test_grade_deterministic_no_checks_defaults_c() -> None:
    trace = _make_trace()
    result = grade_deterministic("dim", DimensionRubric(
        weight=0.5, type="deterministic", criteria={"A": "", "B": "", "C": ""},
    ), trace, [])
    assert result.grade == "C"


class _FakeJudge:
    """Fake judge that always returns a fixed grade."""

    def __init__(self, grade: str = "B") -> None:
        self._grade = grade

    async def grade_dimension(
        self, name: str, rubric: DimensionRubric, trace: AgentTrace,
    ) -> DimensionGrade:
        from app.evals.grading import grade_to_score
        return DimensionGrade(
            name=name, grade=self._grade,
            score=grade_to_score(self._grade),
            weight=rubric.weight, justification="fake",
        )


@pytest.mark.asyncio
async def test_evaluate_level_llm_judge() -> None:
    rubric = _make_rubric("llm_judge")
    trace = _make_trace()
    result = await evaluate_level(rubric, trace, _FakeJudge("B"))  # type: ignore[arg-type]
    assert result.grade == "B"
    assert result.weighted_score == 0.7


@pytest.mark.asyncio
async def test_evaluate_level_hybrid_passes() -> None:
    rubric = RubricConfig(
        level=1, name="T", prompt="p", prompt_sequence=[],
        dimensions={"dim": DimensionRubric(
            weight=1.0, type="hybrid",
            criteria={"A": "", "B": "", "C": ""},
            deterministic=["has output"],
        )},
        grading_thresholds={"A": 0.85, "B": 0.60, "C": 0.40},
    )
    trace = _make_trace("has output here")
    checks = {"dim": [lambda t: "output" in t.final_output]}
    result = await evaluate_level(rubric, trace, _FakeJudge("A"), checks)  # type: ignore[arg-type]
    assert result.grade == "A"  # deterministic passed → use LLM grade


@pytest.mark.asyncio
async def test_evaluate_level_hybrid_fails_deterministic() -> None:
    rubric = RubricConfig(
        level=1, name="T", prompt="p", prompt_sequence=[],
        dimensions={"dim": DimensionRubric(
            weight=1.0, type="hybrid",
            criteria={"A": "", "B": "", "C": ""},
            deterministic=["must have xyz"],
        )},
        grading_thresholds={"A": 0.85, "B": 0.60, "C": 0.40},
    )
    trace = _make_trace("no match")
    checks = {"dim": [lambda t: "xyz" in t.final_output]}
    result = await evaluate_level(rubric, trace, _FakeJudge("A"), checks)  # type: ignore[arg-type]
    assert result.grade == "F"  # deterministic failed → F


def test_format_level_result() -> None:
    dims = [
        DimensionGrade(name="chart", grade="B", score=0.7, weight=0.5, justification=""),
        DimensionGrade(name="table", grade="A", score=1.0, weight=0.5, justification=""),
    ]
    result = LevelResult(level=1, name="Basic Rendering", dimensions=dims,
                         weighted_score=0.85, grade="A")
    text = format_level_result(result)
    assert "Level 1" in text
    assert "Basic Rendering" in text
    assert "chart:B" in text
    assert "table:A" in text


def test_format_eval_result() -> None:
    levels = [
        LevelResult(level=1, name="L1", dimensions=[], weighted_score=0.7, grade="B"),
        LevelResult(level=2, name="L2", dimensions=[], weighted_score=0.9, grade="A"),
    ]
    result = EvalResult(levels=levels, overall_score=0.8, overall_grade="B")
    text = format_eval_result(result)
    assert "Overall:" in text
    assert "B" in text
