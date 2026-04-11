from __future__ import annotations

import pytest

from app.evals.judge import JudgeConfig, LLMJudge
from app.evals.rubric import DimensionRubric
from app.evals.types import AgentTrace


def test_judge_config_defaults() -> None:
    config = JudgeConfig()
    assert config.model == "qwen3.5:9b"
    assert config.base_url == "http://localhost:11434"
    assert config.temperature == 0.0


def test_judge_build_prompt() -> None:
    judge = LLMJudge(config=JudgeConfig())
    rubric = DimensionRubric(
        weight=0.3,
        type="llm_judge",
        criteria={"A": "Excellent", "B": "Good", "C": "OK"},
    )
    trace = AgentTrace(
        queries=["SELECT 1"],
        intermediate=[],
        final_output="Here is my analysis.",
        token_count=100,
        duration_ms=500,
        errors=["minor warning"],
    )
    prompt = judge.build_prompt("chart_quality", rubric, trace)
    assert "chart_quality" in prompt
    assert "Here is my analysis." in prompt
    assert "SELECT 1" in prompt
    assert "Excellent" in prompt
    assert "minor warning" in prompt


def test_judge_parse_response_valid() -> None:
    judge = LLMJudge()
    grade, justification = judge.parse_response(
        "GRADE: B — Axes labeled and amounts accurate"
    )
    assert grade == "B"
    assert "Axes labeled" in justification


def test_judge_parse_response_multiline() -> None:
    judge = LLMJudge()
    grade, justification = judge.parse_response(
        "Some preamble text\nGRADE: A — Perfect output\nMore text"
    )
    assert grade == "A"
    assert "Perfect output" in justification


def test_judge_parse_response_invalid_falls_to_f() -> None:
    judge = LLMJudge()
    grade, justification = judge.parse_response("I don't know how to grade this")
    assert grade == "F"
    assert "Could not parse" in justification


def test_judge_parse_response_invalid_letter() -> None:
    judge = LLMJudge()
    grade, justification = judge.parse_response("GRADE: Z — Not a real grade")
    assert grade == "F"


@pytest.mark.asyncio
async def test_judge_grade_dimension_with_mocked_call(monkeypatch: pytest.MonkeyPatch) -> None:
    judge = LLMJudge()

    async def fake_call(self: LLMJudge, prompt: str) -> str:
        return "GRADE: B — Good work"

    monkeypatch.setattr(LLMJudge, "_call_ollama", fake_call)

    rubric = DimensionRubric(
        weight=0.3,
        type="llm_judge",
        criteria={"A": "Excellent", "B": "Good", "C": "OK"},
    )
    trace = AgentTrace(
        queries=[], intermediate=[], final_output="output",
        token_count=0, duration_ms=0, errors=[],
    )
    result = await judge.grade_dimension("test_dim", rubric, trace)
    assert result.grade == "B"
    assert result.score == 0.7
    assert result.weight == 0.3
    assert result.name == "test_dim"
