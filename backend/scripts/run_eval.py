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

from app.evals.judge import FallbackJudge, LLMJudge, OpenRouterJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level
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

    print(f"\n  Final output preview:")
    preview = trace.final_output[:400]
    for line in preview.splitlines():
        print(f"    {line}")
    if len(trace.final_output) > 400:
        print(f"    … ({len(trace.final_output)} chars total)")

    if not use_judge or judge is None:
        print(f"\n  [judge skipped — pass --judge to enable LLM grading]")
        return

    print(f"\n  Grading…")
    checks = LEVEL_CHECKS.get(level, {})
    try:
        result = await evaluate_level(rubric, trace, judge, checks)
        print(f"\n  {'─' * 68}")
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

    judge: OpenRouterJudge | LLMJudge | FallbackJudge | None = None
    if use_judge:
        judge = OpenRouterJudge()
        print(f"✓ Judge: OpenRouter ({judge._config.model})")
    else:
        print("  Judge: disabled (pass --judge to enable LLM grading)")

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
