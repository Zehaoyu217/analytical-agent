"""Core types for the agent evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


# ── Trace analysis (judge-free) ───────────────────────────────────────────────

@dataclass(frozen=True)
class StepBreakdown:
    """What the agent actually did, tool-by-tool."""
    tool_counts: dict[str, int]    # {"execute_python": 12, "write_working": 3}
    completed: bool                # True if final_output is non-empty
    steps_exhausted: bool          # True when many queries but no completion


@dataclass(frozen=True)
class QueryResult:
    """One execute_python invocation, parsed from the trace."""
    code: str
    tables_accessed: list[str]
    had_error: bool
    error_text: str


@dataclass(frozen=True)
class ErrorPattern:
    """A classified failure pattern found in the trace."""
    kind: str        # "df_none_misuse" | "max_steps_exhausted" | etc.
    evidence: str    # raw snippet that triggered the pattern
    suggestion: str  # concrete fix recommendation


@dataclass(frozen=True)
class TraceAnalysis:
    """Full diagnostic report produced by TraceAnalyzer — no LLM required."""
    completion: Literal["complete", "exhausted", "empty", "errored"]
    step_breakdown: StepBreakdown
    query_results: list[QueryResult]
    check_results: dict[str, bool]         # check_name → passed
    error_patterns: list[ErrorPattern]
    root_cause: str
    suggestions: list[str]


# ── Agent execution trace ─────────────────────────────────────────────────────

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
