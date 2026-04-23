"""Shared fixtures for agent evaluation tests.

These tests run the full grading pipeline with a mock agent.
They require the local MLX judge model to be cached and loadable.

The `_require_local_judge` autouse fixture probes the local judge once
per session and skips every test in this dir when it's unreachable —
so `pytest tests/` is green on a laptop with no local LLM running.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import JudgeConfig, LLMJudge, local_judge_ready_reason
from app.evals.types import AgentTrace

RUBRICS_DIR = Path(__file__).parent / "rubrics"
_REQUIRED_MODEL = JudgeConfig().model

# Resolved once per session so we don't re-probe for every test.
# Value is None (unchecked), "" (ready), or a skip-reason string.
_judge_skip_reason_cache: str | None = None
_CACHE_SENTINEL_READY = ""


def _judge_skip_reason() -> str:
    """Return an empty string if the local MLX judge is ready, otherwise a reason."""

    global _judge_skip_reason_cache
    if _judge_skip_reason_cache is None:
        _judge_skip_reason_cache = local_judge_ready_reason(_REQUIRED_MODEL)
    return _judge_skip_reason_cache


@pytest.fixture(autouse=True)
def _require_local_judge() -> None:
    """Skip the eval tests if the local judge isn't ready."""

    reason = _judge_skip_reason()
    if reason:
        pytest.skip(f"{reason}; skipping LLM-judged eval")


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
    """LLM judge using default MLX config."""
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
