"""Core types for the agent evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AgentTrace:
    """Captured trace of an agent's execution."""

    queries: list[str]
    intermediate: list[Any]
    final_output: str
    token_count: int
    duration_ms: int
    errors: list[str]


@runtime_checkable
class AgentInterface(Protocol):
    """Protocol that all agent implementations must satisfy."""

    async def run(self, prompt: str, db_path: str) -> AgentTrace: ...


@dataclass(frozen=True)
class DimensionGrade:
    """Grade for a single rubric dimension."""

    name: str
    grade: str  # A, B, C, F
    score: float  # A=1.0, B=0.7, C=0.4, F=0.0
    weight: float
    justification: str


@dataclass(frozen=True)
class LevelResult:
    """Graded result for one evaluation level."""

    level: int
    name: str
    dimensions: list[DimensionGrade]
    weighted_score: float
    grade: str  # A, B, C, F


@dataclass(frozen=True)
class EvalResult:
    """Aggregate result across all evaluation levels."""

    levels: list[LevelResult]
    overall_score: float
    overall_grade: str  # A, B, C, F
