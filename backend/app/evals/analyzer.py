"""Trace-based diagnostic analysis for the eval improvement loop.

TraceAnalyzer produces a TraceAnalysis from a raw AgentTrace without any
LLM judge.  It classifies error patterns, runs deterministic checks, infers
a root cause, and emits concrete suggestions — everything needed to iterate
on agent behavior between runs.

Usage::

    from app.evals.analyzer import TraceAnalyzer

    analysis = TraceAnalyzer().analyze(trace, checks=LEVEL_CHECKS.get(level, {}))
    print_trace_analysis(analysis)   # in run_eval.py
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.evals.types import (
    AgentTrace,
    ErrorPattern,
    QueryResult,
    StepBreakdown,
    TraceAnalysis,
)

# ── Error pattern registry ────────────────────────────────────────────────────
# Each entry: (kind, detect(trace) -> evidence | None, suggestion)
# Returns non-None evidence string when the pattern fires.

_STEPS_EXHAUSTED_THRESHOLD = 15  # queries at or above this with empty output


def _detect_df_none_misuse(trace: AgentTrace) -> str | None:
    # profile(df['x']) or profile(df=...) when df is None
    for err in trace.errors:
        if "NoneType" in err and ("profile" in err or "df[" in err):
            return err[:200]
    for q in trace.queries:
        if re.search(r"profile\s*\(\s*df\s*[\[\(]", q):
            snippet = q.strip()[:120]
            return f"query: {snippet}"
    return None


def _detect_profile_string_arg(trace: AgentTrace) -> str | None:
    for q in trace.queries:
        if re.search(r"profile\s*\(\s*['\"]", q) or re.search(r"profile\s*\(\s*df\s*=\s*['\"]", q):
            return q.strip()[:120]
    return None


def _detect_max_steps_exhausted(trace: AgentTrace) -> str | None:
    if len(trace.queries) >= _STEPS_EXHAUSTED_THRESHOLD and not trace.final_output.strip():
        return f"{len(trace.queries)} queries executed, final_output empty"
    return None


def _detect_early_bail(trace: AgentTrace) -> str | None:
    if len(trace.queries) == 0 and not trace.final_output.strip():
        return "no execute_python calls made, no output produced"
    return None


def _detect_duckdb_syntax(trace: AgentTrace) -> str | None:
    for err in trace.errors:
        low = err.lower()
        if any(kw in low for kw in ("catalog error", "parser error", "binder error", "syntax error")):
            return err[:200]
    return None


def _detect_no_synthesis(trace: AgentTrace) -> str | None:
    # Many queries but empty output, and not already caught by max_steps
    if (
        len(trace.queries) >= 5
        and not trace.final_output.strip()
        and len(trace.queries) < _STEPS_EXHAUSTED_THRESHOLD
    ):
        return f"{len(trace.queries)} queries ran but no final response written"
    return None


def _detect_missing_table(trace: AgentTrace) -> str | None:
    for err in trace.errors:
        if "table" in err.lower() and ("not found" in err.lower() or "does not exist" in err.lower()):
            return err[:200]
    return None


_PATTERN_REGISTRY: list[tuple[str, Callable[[AgentTrace], str | None], str]] = [
    (
        "df_none_misuse",
        _detect_df_none_misuse,
        "Tool description already updated — re-run to verify fix. "
        "Model should use conn.execute('SELECT * FROM x').df() instead of df['x'].",
    ),
    (
        "profile_wrong_arg",
        _detect_profile_string_arg,
        "Model passed a string to profile() instead of a DataFrame. "
        "Check that _EXECUTE_PYTHON description shows profile(conn.execute(...).df(), name=...) example.",
    ),
    (
        "max_steps_exhausted",
        _detect_max_steps_exhausted,
        "Agent consumed all available steps on tool calls without a synthesis turn. "
        "Options: (1) raise _DEFAULT_MAX_STEPS, (2) split multi-part prompt into sequential runs, "
        "(3) add 'always respond after N queries' to system prompt.",
    ),
    (
        "early_bail",
        _detect_early_bail,
        "Agent produced no output and ran no queries. "
        "System prompt may be overly restrictive, or the model refused the task.",
    ),
    (
        "duckdb_syntax",
        _detect_duckdb_syntax,
        "DuckDB query failed with a syntax or catalog error. "
        "Check SQL generated against actual table/column names in eval.db.",
    ),
    (
        "no_final_synthesis",
        _detect_no_synthesis,
        "Agent ran queries but never wrote a final response. "
        "May need explicit instruction: 'After gathering data, always write a markdown response.'",
    ),
    (
        "missing_table",
        _detect_missing_table,
        "Agent referenced a table that does not exist in eval.db. "
        "Verify tool description lists all available tables accurately.",
    ),
]


# ── Query result extraction ───────────────────────────────────────────────────

_TABLE_PATTERN = re.compile(
    r"(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)


def _extract_tables(code: str) -> list[str]:
    return list(dict.fromkeys(m.group(1).lower() for m in _TABLE_PATTERN.finditer(code)))


def _parse_query_results(trace: AgentTrace) -> list[QueryResult]:
    results: list[QueryResult] = []
    for i, code in enumerate(trace.queries):
        # Match error to query by index (errors list is tool-level, not per-query)
        # We can only detect if any error message references the code snippet
        code_snippet = code.strip()[:80]
        had_error = any(code_snippet[:40] in err for err in trace.errors)
        error_text = next(
            (err for err in trace.errors if code_snippet[:40] in err), ""
        )
        results.append(QueryResult(
            code=code,
            tables_accessed=_extract_tables(code),
            had_error=had_error,
            error_text=error_text[:200],
        ))
    return results


# ── Step breakdown ────────────────────────────────────────────────────────────

def _build_step_breakdown(trace: AgentTrace) -> StepBreakdown:
    # Count tool calls from intermediate artifacts if available,
    # otherwise infer: execute_python count from queries, write_working from intermediate
    tool_counts: dict[str, int] = {}

    # Count execute_python from queries list
    if trace.queries:
        tool_counts["execute_python"] = len(trace.queries)

    # Count other tools from intermediate list
    for item in trace.intermediate:
        if isinstance(item, dict):
            tool_name = item.get("tool", "unknown")
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    completed = bool(trace.final_output.strip())
    steps_exhausted = (
        len(trace.queries) >= _STEPS_EXHAUSTED_THRESHOLD and not completed
    )

    return StepBreakdown(
        tool_counts=tool_counts,
        completed=completed,
        steps_exhausted=steps_exhausted,
    )


# ── Completion status ─────────────────────────────────────────────────────────

def _completion_status(trace: AgentTrace, step_breakdown: StepBreakdown) -> str:
    if step_breakdown.completed:
        return "complete"
    if step_breakdown.steps_exhausted:
        return "exhausted"
    if trace.errors and not trace.final_output.strip():
        return "errored"
    return "empty"


# ── Root cause inference ──────────────────────────────────────────────────────

def _infer_root_cause(
    completion: str,
    patterns: list[ErrorPattern],
    trace: AgentTrace,
) -> str:
    if completion == "complete" and not patterns:
        return "Run completed successfully with no detected error patterns."

    if completion == "complete" and patterns:
        kinds = ", ".join(p.kind for p in patterns)
        return (
            f"Run completed but {len(patterns)} warning pattern(s) detected: {kinds}. "
            "Output was produced — verify quality."
        )

    primary = patterns[0] if patterns else None

    if primary and primary.kind == "max_steps_exhausted":
        step_count = len(trace.queries)
        error_count = len(trace.errors)
        waste = f" {error_count} error(s) wasted steps on retry loops." if error_count else ""
        return (
            f"Agent exhausted all {step_count} available steps without producing a response.{waste} "
            "The prompt may require more steps than the current max, or error retries consumed the budget."
        )

    if primary and primary.kind in ("df_none_misuse", "profile_wrong_arg"):
        return (
            "Agent repeatedly called profile() with incorrect arguments (df=None or string). "
            "Each failure triggered a retry, burning multiple steps. "
            "Root fix: verify updated _EXECUTE_PYTHON tool description is in effect."
        )

    if primary and primary.kind == "early_bail":
        return (
            "Agent produced no output and made no tool calls. "
            "Likely the model refused the task or the system prompt is blocking execution."
        )

    if primary and primary.kind == "duckdb_syntax":
        return (
            "Agent generated invalid SQL that DuckDB rejected. "
            "Check column/table names in the generated queries against eval.db schema."
        )

    if completion == "errored":
        err_preview = trace.errors[0][:100] if trace.errors else "unknown"
        return f"Run ended with errors and no output. First error: {err_preview}"

    return (
        f"Run ended without output after {len(trace.queries)} queries. "
        "Agent may have stalled before the synthesis step."
    )


# ── Suggestion assembly ───────────────────────────────────────────────────────

def _build_suggestions(
    completion: str,
    patterns: list[ErrorPattern],
    trace: AgentTrace,
    check_results: dict[str, bool],
) -> list[str]:
    suggestions: list[str] = []

    # From error patterns
    for p in patterns:
        suggestions.append(p.suggestion)

    # From failed checks
    failed_checks = [name for name, passed in check_results.items() if not passed]
    if failed_checks and completion == "complete":
        suggestions.append(
            f"Output missing expected content for: {', '.join(failed_checks)}. "
            "Re-read final_output — agent may have produced partial results."
        )

    # Generic: empty output with no patterns
    if completion in ("empty", "exhausted") and not patterns:
        suggestions.append(
            "Add 'After analysis, always write a final markdown response' to system prompt."
        )

    # Token efficiency
    if trace.token_count > 50_000:
        suggestions.append(
            f"High token usage ({trace.token_count:,}). "
            "Consider reducing context size or capping at earlier steps."
        )

    return suggestions


# ── Public API ────────────────────────────────────────────────────────────────

DeterministicCheck = Callable[[AgentTrace], bool]


class TraceAnalyzer:
    """Produces a TraceAnalysis from a raw AgentTrace — no LLM required."""

    def analyze(
        self,
        trace: AgentTrace,
        checks: dict[str, list[DeterministicCheck]] | None = None,
    ) -> TraceAnalysis:
        """Analyze a trace and return a full diagnostic report.

        Args:
            trace:  The captured agent execution trace.
            checks: Optional dict of check_name → [lambda trace: bool].
                    Same format as LEVEL_CHECKS in run_eval.py.
        """
        checks = checks or {}

        step_breakdown = _build_step_breakdown(trace)
        query_results = _parse_query_results(trace)
        completion = _completion_status(trace, step_breakdown)

        # Run error pattern detection
        error_patterns: list[ErrorPattern] = []
        for kind, detect, suggestion in _PATTERN_REGISTRY:
            evidence = detect(trace)
            if evidence is not None:
                error_patterns.append(ErrorPattern(
                    kind=kind,
                    evidence=evidence,
                    suggestion=suggestion,
                ))

        # Run deterministic checks
        check_results: dict[str, bool] = {}
        for check_name, check_fns in checks.items():
            if not check_fns:
                check_results[check_name] = True
                continue
            check_results[check_name] = all(fn(trace) for fn in check_fns)

        root_cause = _infer_root_cause(completion, error_patterns, trace)
        suggestions = _build_suggestions(completion, error_patterns, trace, check_results)

        return TraceAnalysis(
            completion=completion,
            step_breakdown=step_breakdown,
            query_results=query_results,
            check_results=check_results,
            error_patterns=error_patterns,
            root_cause=root_cause,
            suggestions=suggestions,
        )
