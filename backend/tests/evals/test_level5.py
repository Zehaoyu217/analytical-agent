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
    # Step 1: loans_summary_v1
    "## loans_summary_v1\n| loan_type | count | avg_principal | default_rate |\n"
    "|-----------|-------|--------------|-------------|\n"
    "| personal | 24 | $17,500 | 20.8% |\n"
    "| auto | 20 | $30,000 | 15.0% |\n"
    "| mortgage | 20 | $300,000 | 10.0% |\n"
    "| business | 16 | $112,500 | 18.8% |",
    # Step 2: loans_summary_v2 — remove auto, add credit score
    "## loans_summary_v2 (auto removed, avg_credit_score added)\n"
    "| loan_type | count | avg_principal | default_rate | avg_credit_score |\n"
    "|-----------|-------|--------------|-------------|------------------|\n"
    "| personal | 24 | $17,500 | 20.8% | 665 |\n"
    "| mortgage | 20 | $300,000 | 10.0% | 738 |\n"
    "| business | 16 | $112,500 | 18.8% | 690 |\n\n"
    "_Diff from loans_summary_v1: dropped auto (20 rows), added avg_credit_score column._",
    # Step 3: txn_summary_v1 — Q4 transactions by category
    "## txn_summary_v1 — Q4 2025 by category\n"
    "| month | payroll | utilities | transfer | merchant | atm | wire |\n"
    "|-------|---------|-----------|----------|----------|-----|------|\n"
    "| Oct | $82K | -$12K | $5K | -$45K | -$8K | $15K |\n"
    "| Nov | $85K | -$13K | $7K | -$68K | -$9K | $12K |\n"
    "| Dec | $88K | -$14K | $3K | -$72K | -$10K | $18K |",
    # Step 4: txn_summary_v2 — combine atm+merchant → cash_and_retail
    "## txn_summary_v2 (atm + merchant → cash_and_retail)\n"
    "| month | payroll | utilities | transfer | cash_and_retail | wire |\n"
    "|-------|---------|-----------|----------|----------------|------|\n"
    "| Oct | $82K | -$12K | $5K | -$53K | $15K |\n"
    "| Nov | $85K | -$13K | $7K | -$77K | $12K |\n"
    "| Dec | $88K | -$14K | $3K | -$82K | $18K |\n\n"
    "_Diff from txn_summary_v1: merged atm + merchant into cash_and_retail (6 cols → 5 cols)._",
    # Step 5: combined_v1 — loans_summary_v2 + txn_summary_v2
    "## combined_v1 — loans_summary_v2 joined with txn_summary_v2\n"
    "| loan_type | count | avg_principal | default_rate | avg_credit_score "
    "| oct_cash_retail | nov_cash_retail | dec_cash_retail |\n"
    "|-----------|-------|--------------|-------------|-----------------|"
    "----------------|----------------|----------------|\n"
    "| personal | 24 | $17,500 | 20.8% | 665 | -$53K | -$77K | -$82K |\n"
    "| mortgage | 20 | $300,000 | 10.0% | 738 | -$53K | -$77K | -$82K |\n"
    "| business | 16 | $112,500 | 18.8% | 690 | -$89K | -$102K | -$109K |\n\n"
    "_Sources: loans_summary_v2 (rows) + txn_summary_v2 (cash_and_retail columns)._",
    # Step 6: ratio_v1 — transaction-to-loan ratio
    "## ratio_v1 — monthly txn volume / outstanding principal by segment\n"
    "| segment | monthly_txn_volume | outstanding_principal | ratio |\n"
    "|---------|-------------------|-----------------------|-------|\n"
    "| retail | $45K | $420K | 0.107 |\n"
    "| business | $89K | $1.8M | 0.049 |\n"
    "| premium | $120K | $3.5M | 0.034 |\n\n"
    "_Derived from combined_v1. Ratio = monthly_txn_volume / outstanding_principal._",
    # Step 7: ratio_v1_filtered — filter ratio > 0.5
    "## ratio_v1_filtered — segments where ratio > 0.5\n\n"
    "No segments meet the threshold (max retail = 0.107). Empty result set.\n\n"
    "_Filter applied to ratio_v1: WHERE ratio > 0.5. All 3 segments below threshold._",
    # Step 8: comparison of full version trail — what changed and why it matters
    "## State Comparison: loans_summary_v1 through ratio_v1_filtered\n\n"
    "**Full version trail:**\n"
    "loans_summary_v1 → loans_summary_v2 → txn_summary_v1 → txn_summary_v2 "
    "→ combined_v1 → ratio_v1 → ratio_v1_filtered\n\n"
    "**loans_summary_v1 (step 1):**\n"
    "4 cols: loan_type, count, avg_principal, default_rate. 4 rows (personal, auto, mortgage, business).\n\n"  # noqa: E501
    "**loans_summary_v2 (step 2):**\n"
    "5 cols: added avg_credit_score. 3 rows: auto removed (was 20 rows, 15.0% default rate, "
    "$30K avg principal). Credit scores reveal mortgage holders are lowest-risk borrowers (738).\n\n"  # noqa: E501
    "**txn_summary_v2 (step 4, from txn_summary_v1):**\n"
    "5 cols: atm + merchant merged into cash_and_retail (was 6 cols). "
    "cash_and_retail grows Oct→Dec ($53K → $82K), driven by holiday spending.\n\n"
    "**ratio_v1 (step 6):**\n"
    "4 cols: segment, monthly_txn_volume, outstanding_principal, ratio. 3 rows. "
    "Retail ratio=0.107, business=0.049, premium=0.034.\n\n"
    "**ratio_v1_filtered (step 7):** 0 rows — no segment exceeds ratio > 0.5.\n\n"
    "**What changed and what it means:**\n"
    "1. Auto removed: excluded the loan type with the smallest principal ($30K). "
    "Retail segment now carries the highest default risk in loans_summary_v2.\n"
    "2. Q4 transaction context added: retail spends most in cash_and_retail relative "
    "to principal — yet ratio (0.107) is far below 0.5. The loan book is not "
    "funded by transaction cash flows in any segment.\n"
    "3. Filter returned empty: the null result is the signal. All segments have "
    "monthly txn volume < 11% of outstanding principal — conservative lending "
    "posture, low short-term liquidity risk. If the filter had returned rows, "
    "those segments would warrant stress-testing for cash-flow dependency.",
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
