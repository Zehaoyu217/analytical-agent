"""Level 5: Stress Test — state tracking under compounding mutations.

Requires Ollama running locally for LLM-judged dimensions.
Run: cd backend && python -m pytest tests/evals/test_level5.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import LLMJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level, format_level_result
from app.evals.types import AgentTrace
from tests.evals.conftest import SequentialMockAgent

STEP_OUTPUTS = [
    # Step 1: loans summary
    "## Loans Summary\n| loan_type | count | avg_principal | default_rate |\n"
    "|-----------|-------|--------------|-------------|\n"
    "| personal | 24 | $17,500 | 20.8% |\n"
    "| auto | 20 | $30,000 | 15.0% |\n"
    "| mortgage | 20 | $300,000 | 10.0% |\n"
    "| business | 16 | $112,500 | 18.8% |",
    # Step 2: remove auto, add credit score
    "## Loans Summary v2 (auto removed, credit score added)\n"
    "| loan_type | count | avg_principal | default_rate | avg_credit_score |\n"
    "|-----------|-------|--------------|-------------|------------------|\n"
    "| personal | 24 | $17,500 | 20.8% | 665 |\n"
    "| mortgage | 20 | $300,000 | 10.0% | 738 |\n"
    "| business | 16 | $112,500 | 18.8% | 690 |",
    # Step 3: Q4 transactions by category
    "## Q4 2025 Transactions by Category\n| month | payroll | utilities | transfer "
    "| merchant | atm | wire |\n|-------|---------|-----------|----------|"
    "----------|-----|------|\n| Oct | $82K | -$12K | $5K | -$45K | -$8K | $15K |\n"
    "| Nov | $85K | -$13K | $7K | -$68K | -$9K | $12K |\n"
    "| Dec | $88K | -$14K | $3K | -$72K | -$10K | $18K |",
    # Step 4: combine atm+merchant
    "## Q4 2025 (atm+merchant → cash_and_retail)\n| month | payroll | utilities "
    "| transfer | cash_and_retail | wire |\n|-------|---------|-----------|"
    "----------|----------------|------|\n| Oct | $82K | -$12K | $5K | -$53K | $15K |\n"
    "| Nov | $85K | -$13K | $7K | -$77K | $12K |\n"
    "| Dec | $88K | -$14K | $3K | -$82K | $18K |",
    # Step 5: combined view
    "## Combined View — Loans + Q4 Transactions\n"
    "| loan_type | count | avg_principal | default_rate | avg_credit_score "
    "| oct_total | nov_total | dec_total |\n"
    "Joined on customer segment where applicable.",
    # Step 6: ratio calculation
    "## Transaction-to-Loan Ratio by Segment\n"
    "| segment | monthly_txn_volume | outstanding_principal | ratio |\n"
    "|---------|-------------------|-----------------------|-------|\n"
    "| retail | $45K | $420K | 0.107 |\n"
    "| business | $89K | $1.8M | 0.049 |\n"
    "| premium | $120K | $3.5M | 0.034 |",
    # Step 7: filter ratio > 0.5
    "## Filtered: Segments with ratio > 0.5\n\nNo segments exceed the 0.5 "
    "threshold. The highest ratio is retail at 0.107. This suggests loan "
    "principals significantly outweigh monthly transaction volumes across "
    "all segments.",
    # Step 8: comparison
    "## Comparison: Final vs Original (Step 1)\n\n"
    "**Changes from Step 1:**\n"
    "1. Auto loans removed — they represented 25% of loans\n"
    "2. Credit scores added — reveals mortgage holders have highest scores (738)\n"
    "3. Transaction context added — shows spending patterns alongside loan risk\n"
    "4. Ratio analysis shows all segments have low txn/principal ratios (<0.11)\n\n"
    "**Key Insight:** The filtering in step 7 revealed that no segment's monthly "
    "transaction volume is particularly high relative to outstanding loan principal. "
    "This means the bank's loan book is well-collateralized relative to transaction "
    "activity — a sign of conservative lending.",
]


@pytest.fixture
def level5_traces() -> list[AgentTrace]:
    return [
        AgentTrace(
            queries=[f"SELECT ... -- step {i + 1}"],
            intermediate=[],
            final_output=output,
            token_count=450,
            duration_ms=3000,
            errors=[],
        )
        for i, output in enumerate(STEP_OUTPUTS)
    ]


@pytest.mark.asyncio
@pytest.mark.slow
async def test_level5_grading(
    rubrics_path: Path,
    eval_db: str,
    llm_judge: LLMJudge,
    level5_traces: list[AgentTrace],
) -> None:
    """Verify Level 5 grading pipeline handles sequential prompts."""
    rubric = load_rubric(rubrics_path / "level5_stress.yaml")

    mock = SequentialMockAgent(level5_traces)

    # Run all 8 prompts sequentially
    all_traces: list[AgentTrace] = []
    for prompt in rubric.prompt_sequence:
        trace = await mock.run(prompt, eval_db)
        all_traces.append(trace)

    # Combine into single trace for grading
    combined = AgentTrace(
        queries=[q for t in all_traces for q in t.queries],
        intermediate=[item for t in all_traces for item in t.intermediate],
        final_output=all_traces[-1].final_output,
        token_count=sum(t.token_count for t in all_traces),
        duration_ms=sum(t.duration_ms for t in all_traces),
        errors=[e for t in all_traces for e in t.errors],
    )

    optimal = rubric.token_budget_optimal or 4000
    total_tokens = combined.token_count

    checks = {
        "step_completion": [
            lambda t, _i=i: len(all_traces) > _i
            for i in range(8)
        ],
        "state_correctness": [
            lambda t: "v2" in t.final_output or "step 1" in t.final_output.lower(),
        ],
        "efficiency": [
            lambda t, _tt=total_tokens, _o=optimal: _tt <= _o * 2.0,
            lambda t, _tt=total_tokens, _o=optimal: _tt <= _o * 1.5,
            lambda t, _tt=total_tokens, _o=optimal: _tt <= _o * 1.2,
        ],
    }

    result = await evaluate_level(rubric, combined, llm_judge, checks)
    print("\n" + format_level_result(result))
    for d in result.dimensions:
        print(f"  {d.name}: {d.grade} — {d.justification}")
    print(f"  token_budget: {total_tokens}/{optimal} ({total_tokens/optimal:.1f}x)")
    assert result.grade != "F", f"Level 5 failed: score={result.weighted_score:.2f}"
