from __future__ import annotations

from app.evals.grading import (
    calculate_weighted_score,
    grade_eval,
    grade_level,
    grade_to_score,
    score_to_grade,
)
from app.evals.types import DimensionGrade, LevelResult


def test_grade_to_score_all_grades() -> None:
    assert grade_to_score("A") == 1.0
    assert grade_to_score("B") == 0.7
    assert grade_to_score("C") == 0.4
    assert grade_to_score("F") == 0.0


def test_grade_to_score_invalid_raises() -> None:
    try:
        grade_to_score("X")
        assert False, "Should have raised"
    except KeyError:
        pass


def test_score_to_grade_thresholds() -> None:
    assert score_to_grade(1.0) == "A"
    assert score_to_grade(0.85) == "A"
    assert score_to_grade(0.84) == "B"
    assert score_to_grade(0.60) == "B"
    assert score_to_grade(0.59) == "C"
    assert score_to_grade(0.40) == "C"
    assert score_to_grade(0.39) == "F"
    assert score_to_grade(0.0) == "F"


def test_calculate_weighted_score() -> None:
    dims = [
        DimensionGrade(name="a", grade="A", score=1.0, weight=0.5, justification=""),
        DimensionGrade(name="b", grade="C", score=0.4, weight=0.5, justification=""),
    ]
    result = calculate_weighted_score(dims)
    assert result == 0.7  # (1.0*0.5 + 0.4*0.5)


def test_calculate_weighted_score_empty() -> None:
    assert calculate_weighted_score([]) == 0.0


def test_grade_level() -> None:
    dims = [
        DimensionGrade(name="x", grade="B", score=0.7, weight=0.6, justification=""),
        DimensionGrade(name="y", grade="A", score=1.0, weight=0.4, justification=""),
    ]
    result = grade_level(1, "Basic", dims)
    assert result.level == 1
    assert result.name == "Basic"
    assert result.weighted_score == 0.82  # 0.7*0.6 + 1.0*0.4
    assert result.grade == "B"  # 0.82 < 0.85


def test_grade_level_perfect() -> None:
    dims = [
        DimensionGrade(name="x", grade="A", score=1.0, weight=1.0, justification=""),
    ]
    result = grade_level(1, "Perfect", dims)
    assert result.grade == "A"


def test_grade_eval() -> None:
    levels = [
        LevelResult(level=1, name="L1", dimensions=[], weighted_score=0.9, grade="A"),
        LevelResult(level=2, name="L2", dimensions=[], weighted_score=0.7, grade="B"),
    ]
    result = grade_eval(levels)
    assert result.overall_score == 0.8  # (0.9 + 0.7) / 2
    assert result.overall_grade == "B"  # 0.80 < 0.85


def test_grade_eval_empty() -> None:
    result = grade_eval([])
    assert result.overall_score == 0.0
    assert result.overall_grade == "F"
