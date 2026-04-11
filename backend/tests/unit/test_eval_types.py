from __future__ import annotations

from app.evals.types import (
    AgentInterface,
    AgentTrace,
    DimensionGrade,
    EvalResult,
    LevelResult,
)


def test_agent_trace_creation() -> None:
    trace = AgentTrace(
        queries=["SELECT 1"],
        intermediate=[{"rows": 10}],
        final_output="Done",
        token_count=100,
        duration_ms=500,
        errors=[],
    )
    assert trace.queries == ["SELECT 1"]
    assert trace.token_count == 100
    assert trace.errors == []


def test_agent_trace_is_frozen() -> None:
    trace = AgentTrace(
        queries=[], intermediate=[], final_output="",
        token_count=0, duration_ms=0, errors=[],
    )
    try:
        trace.token_count = 999  # type: ignore[misc]
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_dimension_grade_creation() -> None:
    grade = DimensionGrade(
        name="chart",
        grade="B",
        score=0.7,
        weight=0.3,
        justification="Axes labeled, amounts accurate",
    )
    assert grade.grade == "B"
    assert grade.score == 0.7
    assert grade.weight == 0.3


def test_level_result_creation() -> None:
    dims = [
        DimensionGrade(name="a", grade="A", score=1.0, weight=0.5, justification=""),
        DimensionGrade(name="b", grade="C", score=0.4, weight=0.5, justification=""),
    ]
    result = LevelResult(
        level=1, name="Basic", dimensions=dims, weighted_score=0.7, grade="B",
    )
    assert result.grade == "B"
    assert result.weighted_score == 0.7
    assert len(result.dimensions) == 2


def test_eval_result_creation() -> None:
    level = LevelResult(
        level=1, name="Basic", dimensions=[], weighted_score=0.7, grade="B",
    )
    result = EvalResult(
        levels=[level], overall_score=0.7, overall_grade="B",
    )
    assert result.overall_grade == "B"
    assert len(result.levels) == 1


class _MockAgent:
    async def run(self, prompt: str, db_path: str) -> AgentTrace:
        return AgentTrace(
            queries=[], intermediate=[], final_output="mock",
            token_count=0, duration_ms=0, errors=[],
        )


def test_agent_interface_protocol_compliance() -> None:
    agent: AgentInterface = _MockAgent()
    assert isinstance(agent, AgentInterface)
