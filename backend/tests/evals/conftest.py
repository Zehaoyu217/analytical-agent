"""Shared fixtures for agent evaluation tests.

These tests run the full grading pipeline with a mock agent.
They require Ollama running locally for LLM-judged dimensions.

The `_require_ollama` autouse fixture probes the Ollama HTTP API once
per session and skips every test in this dir when it's unreachable —
so `pytest tests/` is green on a laptop with no local LLM running.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from app.evals.judge import LLMJudge
from app.evals.types import AgentTrace

RUBRICS_DIR = Path(__file__).parent / "rubrics"
_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_PROBE_TIMEOUT_S = 0.5

# Resolved once per session so we don't re-probe for every test.
_ollama_available_cache: bool | None = None


def _ollama_available() -> bool:
    global _ollama_available_cache
    if _ollama_available_cache is None:
        try:
            resp = httpx.get(
                f"{_OLLAMA_URL}/api/tags",
                timeout=_OLLAMA_PROBE_TIMEOUT_S,
            )
            _ollama_available_cache = resp.status_code == 200
        except (httpx.HTTPError, OSError):
            _ollama_available_cache = False
    return _ollama_available_cache


@pytest.fixture(autouse=True)
def _require_ollama() -> None:
    """Skip the eval tests if Ollama isn't reachable — the judge calls need it."""
    if not _ollama_available():
        pytest.skip(f"Ollama not reachable at {_OLLAMA_URL}; skipping LLM-judged eval")


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
