"""Shared fixtures for agent evaluation tests.

These tests run the full grading pipeline with a mock agent.
They require Ollama running locally for LLM-judged dimensions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import LLMJudge
from app.evals.types import AgentTrace

RUBRICS_DIR = Path(__file__).parent / "rubrics"


@pytest.fixture
def rubrics_path() -> Path:
    """Path to the rubrics directory."""
    return RUBRICS_DIR


@pytest.fixture
def eval_db(tmp_path: Path) -> str:
    """Seed a fresh eval database and return its path."""
    from scripts.seed_eval_data import seed_all

    db_path = tmp_path / "eval.db"
    seed_all(db_path)
    return str(db_path)


@pytest.fixture
def llm_judge() -> LLMJudge:
    """LLM judge using default Ollama config."""
    return LLMJudge()


class MockAgent:
    """Returns a fixed trace for any prompt."""

    def __init__(self, trace: AgentTrace) -> None:
        self._trace = trace

    async def run(self, prompt: str, db_path: str) -> AgentTrace:
        return self._trace


class SequentialMockAgent:
    """Returns different traces for sequential calls (Level 5)."""

    def __init__(self, traces: list[AgentTrace]) -> None:
        self._traces = traces
        self._index = 0

    async def run(self, prompt: str, db_path: str) -> AgentTrace:
        trace = self._traces[min(self._index, len(self._traces) - 1)]
        self._index += 1
        return trace
