"""Level 2: Multi-Step Exploration — analytical chaining and conclusions.

Requires the local MLX judge model for LLM-judged dimensions.
Run: cd backend && python -m pytest tests/evals/test_level2.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import LLMJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level, format_level_result
from app.evals.types import AgentTrace

LEVEL2_RESPONSE = """\
## Analysis: Loan Default Rate by Customer Segment

### Step 1: Default Rate by Segment

| Segment | Total Loans | Defaults | Default Rate |
|---------|-------------|----------|-------------|
| retail | 38 | 8 | 21.1% |
| business | 25 | 4 | 16.0% |
| premium | 17 | 2 | 11.8% |

Retail has the highest default rate at 21.1%.

### Step 2: Credit Score Distribution by Segment

| Segment | Avg Credit Score | Min | Max |
|---------|-----------------|-----|-----|
| retail | 648 | 580 | 749 |
| business | 701 | 630 | 800 |
| premium | 752 | 680 | 850 |

Retail has significantly lower credit scores. This could explain defaults.

### Step 3: Default Rate by Credit Score Bucket

| Credit Bucket | Default Rate |
|---------------|-------------|
| 580-649 | 28.6% |
| 650-719 | 14.3% |
| 720-850 | 5.9% |

Strong inverse relationship: lower credit score = higher default rate.

### Step 4: Controlling for Credit Score — Default Rate by Region

| Region | Default Rate | Avg Credit Score |
|--------|-------------|-----------------|
| southeast | 22.7% | 680 |
| midwest | 16.7% | 695 |
| northeast | 13.3% | 710 |
| west | 10.5% | 715 |

Southeast has higher defaults even after accounting for credit scores.

### Step 5: Conclusion

**Credit score is the primary driver of loan default rate.** The default rate \
drops from 28.6% (score <650) to 5.9% (score >720). Retail customers default \
more because they have lower credit scores on average (648 vs 752 for premium), \
not because of their segment per se.

Region is a secondary factor — southeast shows elevated defaults even \
controlling for credit score, suggesting regional economic conditions play a role.

Loan type has minimal independent effect once credit score is controlled for.\
"""


@pytest.fixture
def level2_trace() -> AgentTrace:
    return AgentTrace(
        queries=[
            "SELECT c.segment, COUNT(*) AS total, "
            "SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) AS defaults "
            "FROM loans l JOIN customers c ON l.customer_id = c.customer_id "
            "GROUP BY c.segment",
            "SELECT c.segment, AVG(c.credit_score), MIN(c.credit_score), "
            "MAX(c.credit_score) FROM customers c "
            "JOIN loans l ON c.customer_id = l.customer_id GROUP BY c.segment",
            "SELECT CASE WHEN credit_score < 650 THEN '580-649' "
            "WHEN credit_score < 720 THEN '650-719' ELSE '720-850' END AS bucket, "
            "AVG(CASE WHEN l.status = 'default' THEN 1.0 ELSE 0.0 END) AS rate "
            "FROM loans l JOIN customers c ON l.customer_id = c.customer_id "
            "GROUP BY bucket ORDER BY bucket",
            "SELECT c.region, AVG(CASE WHEN l.status = 'default' THEN 1.0 ELSE 0.0 END), "
            "AVG(c.credit_score) FROM loans l JOIN customers c "
            "ON l.customer_id = c.customer_id GROUP BY c.region ORDER BY 2 DESC",
        ],
        intermediate=[],
        final_output=LEVEL2_RESPONSE,
        token_count=600,
        duration_ms=8000,
        errors=[],
    )


@pytest.mark.asyncio
async def test_level2_grading(
    rubrics_path: Path,
    eval_db: str,
    llm_judge: LLMJudge,
    level2_trace: AgentTrace,
) -> None:
    """Verify Level 2 grading pipeline produces a non-F result."""
    rubric = load_rubric(rubrics_path / "level2_exploration.yaml")

    checks = {
        "correctness": [
            lambda t: "credit score" in t.final_output.lower()
            and "primary" in t.final_output.lower(),
        ],
    }

    result = await evaluate_level(rubric, level2_trace, llm_judge, checks)
    print("\n" + format_level_result(result))
    for d in result.dimensions:
        print(f"  {d.name}: {d.grade} — {d.justification}")
    assert result.grade != "F", f"Level 2 failed: score={result.weighted_score:.2f}"
