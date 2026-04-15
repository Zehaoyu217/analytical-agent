#!/usr/bin/env python3
"""Run real eval prompts against the live backend and print scored results.

Usage:
    cd backend
    uv run python scripts/run_eval.py              # all levels
    uv run python scripts/run_eval.py --levels 1 2 # specific levels
    uv run python scripts/run_eval.py --no-judge   # skip LLM grading

Requires:
    - Backend running at http://localhost:8000
    - Eval DB seeded at /tmp/eval_run.db (or set EVAL_DB env var)
      Seed: uv run python -c "from pathlib import Path; from scripts.seed_eval_data import seed_all; seed_all(Path('/tmp/eval_run.db'))"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.evals.analyzer import TraceAnalyzer
from app.evals.judge import FallbackJudge, LLMJudge, OpenRouterJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level
from app.evals.types import TraceAnalysis
from tests.evals.real_agent import BackendNotReachableError, RealAgentAdapter

RUBRICS_DIR = Path(__file__).parent.parent / "tests" / "evals" / "rubrics"

LEVELS = {
    1: "level1_rendering.yaml",
    2: "level2_exploration.yaml",
    3: "level3_anomaly.yaml",
    4: "level4_free_explore.yaml",
    5: "level5_stress.yaml",
}

# Deterministic check lambdas per level (mirrors the pytest tests)
LEVEL_CHECKS: dict[int, dict] = {
    1: {
        "table_correctness": [
            lambda t: t.final_output.count("$") >= 10,
            lambda t: "Top 10" in t.final_output or "top 10" in t.final_output.lower(),
        ],
        "mermaid_erd": [
            lambda t: "```mermaid" in t.final_output,
            lambda t: "erDiagram" in t.final_output,
            lambda t: all(
                name in t.final_output
                for name in ["customers", "accounts", "transactions", "loans"]
            ),
        ],
    },
    2: {
        "correctness": [
            lambda t: "credit score" in t.final_output.lower(),
        ],
    },
    3: {},
    4: {},
    5: {},
}


def _bar(score: float, width: int = 30) -> str:
    filled = int(score * width)
    return "█" * filled + "░" * (width - filled)


_STATUS_ICON = {
    "complete": "✓",
    "exhausted": "⚠",
    "empty": "✗",
    "errored": "✗",
}


def _print_analysis(analysis: TraceAnalysis, trace_duration_s: float) -> None:
    """Print a human-readable diagnostic report from a TraceAnalysis."""
    status_icon = _STATUS_ICON.get(analysis.completion, "?")
    status_label = analysis.completion.upper()

    tool_summary = "  ".join(
        f"{name} ×{count}"
        for name, count in sorted(analysis.step_breakdown.tool_counts.items())
    )
    query_errors = sum(1 for qr in analysis.query_results if qr.had_error)
    query_ok = len(analysis.query_results) - query_errors

    print(f"\n  Status:   {status_icon} {status_label}  ({trace_duration_s:.1f}s)")
    print(f"  Tools:    {tool_summary or '(none)'}")
    if analysis.query_results:
        print(f"  Queries:  {query_ok} succeeded, {query_errors} errored")

    if analysis.error_patterns:
        print(f"\n  Errors detected:")
        for p in analysis.error_patterns:
            print(f"    ✗ [{p.kind}]  {p.evidence[:80]}")

    if analysis.check_results:
        print(f"\n  Checks:")
        for name, passed in analysis.check_results.items():
            icon = "✓" if passed else "✗"
            print(f"    {icon} {name}")

    print(f"\n  Root cause:")
    for line in analysis.root_cause.splitlines():
        print(f"    {line}")

    if analysis.suggestions:
        print(f"\n  Suggestions:")
        for i, s in enumerate(analysis.suggestions, 1):
            # Wrap long suggestions at 80 chars
            words, line_buf = s.split(), []
            lines: list[str] = []
            for word in words:
                if sum(len(w) + 1 for w in line_buf) + len(word) > 78:
                    lines.append(" ".join(line_buf))
                    line_buf = [word]
                else:
                    line_buf.append(word)
            if line_buf:
                lines.append(" ".join(line_buf))
            print(f"    {i}. {lines[0]}")
            for continuation in lines[1:]:
                print(f"       {continuation}")


async def run_level(
    level: int,
    adapter: RealAgentAdapter,
    db_path: str,
    judge: OpenRouterJudge | LLMJudge | FallbackJudge | None,
    use_judge: bool,
) -> None:
    rubric_file = RUBRICS_DIR / LEVELS[level]
    rubric = load_rubric(rubric_file)
    # Level 5 uses a prompt_sequence (multi-turn stress test).
    # For the eval runner we concatenate all steps into one prompt.
    if rubric.prompt:
        prompt = rubric.prompt
    elif rubric.prompt_sequence:
        prompt = "\n\n".join(
            f"Step {i+1}: {p}" for i, p in enumerate(rubric.prompt_sequence)
        )
    else:
        print(f"  ⚠ Level {level} has no prompt — skipping")
        return

    print(f"\n{'═' * 70}")
    print(f"  LEVEL {level}: {rubric.name.upper()}")
    print(f"{'═' * 70}")
    print(f"  Prompt: {prompt[:120]}{'…' if len(prompt) > 120 else ''}")
    print(f"{'─' * 70}")
    print("  Sending to backend… (watch the session in http://localhost:5173)")
    t0 = time.monotonic()

    trace = await adapter.run(prompt=prompt)

    elapsed = time.monotonic() - t0
    print(f"  ✓ Agent responded in {elapsed:.1f}s — {trace.token_count} tokens")
    if trace.errors:
        print(f"  ⚠ Errors: {trace.errors}")
    if trace.queries:
        print(f"  Queries run ({len(trace.queries)}):")
        for i, q in enumerate(trace.queries, 1):
            print(f"    [{i}] {q[:100]}{'…' if len(q) > 100 else ''}")

    if trace.final_output:
        print(f"\n  Final output preview:")
        preview = trace.final_output[:400]
        for line in preview.splitlines():
            print(f"    {line}")
        if len(trace.final_output) > 400:
            print(f"    … ({len(trace.final_output)} chars total)")

    # ── Trace analysis (always) ───────────────────────────────────────────────
    checks = LEVEL_CHECKS.get(level, {})
    analysis = TraceAnalyzer().analyze(trace, checks=checks)
    print(f"\n  {'─' * 68}")
    print(f"  TRACE ANALYSIS")
    print(f"  {'─' * 68}")
    _print_analysis(analysis, elapsed)

    # ── LLM grading (only if --judge) ─────────────────────────────────────────
    if not use_judge or judge is None:
        return

    print(f"\n  {'─' * 68}")
    print(f"  JUDGE GRADES")
    print(f"  {'─' * 68}")
    try:
        result = await evaluate_level(rubric, trace, judge, checks)
        print(f"  SCORE: {result.weighted_score:.2f}  GRADE: {result.grade}  [{_bar(result.weighted_score)}]")
        print(f"  {'─' * 68}")
        for d in result.dimensions:
            print(f"  {d.name:<25} {d.grade}  {d.justification[:55]}")
        print(f"  {'─' * 68}")
    except Exception as exc:
        print(f"  ⚠ Grading failed: {exc}")


async def main(levels: list[int], use_judge: bool, db_path: str) -> None:
    adapter = RealAgentAdapter(base_url="http://localhost:8000")

    if not await adapter.health_check():
        print("✗ Backend not reachable at http://localhost:8000 — run 'make backend'")
        sys.exit(1)

    print("✓ Backend reachable")
    print(f"✓ Eval DB: {db_path}")
    print(f"✓ Levels to run: {levels}")

    print("✓ Trace analysis: always enabled")

    judge: OpenRouterJudge | LLMJudge | FallbackJudge | None = None
    if use_judge:
        judge = OpenRouterJudge()
        print(f"✓ LLM judge: OpenRouter ({judge._config.model})")
    else:
        print("  LLM judge: disabled (pass --judge to add letter grades)")

    for level in levels:
        try:
            await run_level(level, adapter, db_path, judge, use_judge)
        except BackendNotReachableError as exc:
            print(f"\n✗ Level {level} failed: {exc}")
        except Exception as exc:
            print(f"\n✗ Level {level} error: {exc!r}")

    print(f"\n{'═' * 70}")
    print("  Done. Sessions visible in http://localhost:5173")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run real eval prompts against live backend")
    parser.add_argument(
        "--levels", nargs="+", type=int, default=list(LEVELS.keys()),
        help="Which levels to run (default: all 5)",
    )
    parser.add_argument(
        "--judge", action="store_true", default=False,
        help="Enable LLM grading via OpenRouter (set OPENROUTER_API_KEY)",
    )
    parser.add_argument(
        "--db", default=os.environ.get("EVAL_DB", "/tmp/eval_run.db"),
        help="Path to eval DuckDB file (default: /tmp/eval_run.db)",
    )
    args = parser.parse_args()

    asyncio.run(main(levels=args.levels, use_judge=args.judge, db_path=args.db))
