"""Level 4: Free Exploration for Insights.

Requires Ollama running locally for LLM-judged dimensions.
Run: cd backend && python -m pytest tests/evals/test_level4.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import LLMJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level, format_level_result
from app.evals.types import AgentTrace

LEVEL4_RESPONSE = """\
## Dataset Exploration — First National Bank

### Data Profile

| Table | Rows | Columns | Notes |
|-------|------|---------|-------|
| customers | 200 | 7 | 3 segments, 4 regions |
| accounts | ~400 | 6 | avg 2 per customer |
| transactions | ~5000 | 8 | 2025 full year |
| loans | 80 | 9 | 4 loan types |
| daily_rates | 365 | 5 | 2025 daily |

### Key Findings

#### 1. Credit Score → Loan Default (Strongest Predictor)
Customers with credit scores below 650 have a 28.6% default rate vs 5.9% for \
scores above 720. This is the single strongest predictor of loan default, \
explaining most of the segment-level variation.

Correlation coefficient: r = -0.72 (strong negative).

#### 2. Regional Delinquency Pattern
Default rates by region: southeast (22.7%) > midwest (16.7%) > northeast \
(13.3%) > west (10.5%). The southeast effect persists even after controlling \
for credit score, suggesting regional economic factors.

#### 3. Premium Customer Paradox
Premium customers have the lowest default rate (11.8%) but the highest average \
loan principal ($187K vs $23K for retail). Lower risk per loan but much higher \
exposure per default event.

#### 4. Seasonal Transaction Patterns
Holiday spending spike: November-December merchant transactions are 50% higher \
than the annual average. July shows a deposit spike from annual bonuses.

#### 5. Fed Rate Environment and Savings
The two fed rate cuts (June, September) correlate with a 12% increase in savings \
account balances in the following months. Customers appear to lock in higher APYs.

#### 6. Dormant Account Age Correlation
85% of dormant accounts belong to customers who joined before 2022. Older \
accounts are more likely to become dormant, suggesting customer lifecycle \
management opportunity.\
"""


@pytest.fixture
def level4_trace() -> AgentTrace:
    return AgentTrace(
        queries=[
            "SELECT table_name, COUNT(*) FROM information_schema.columns GROUP BY 1",
            "SELECT segment, COUNT(*), AVG(credit_score) FROM customers GROUP BY 1",
            "SELECT c.credit_score / 50 * 50 AS bucket, "
            "AVG(CASE WHEN l.status='default' THEN 1.0 ELSE 0.0 END) "
            "FROM loans l JOIN customers c ON l.customer_id=c.customer_id "
            "GROUP BY 1 ORDER BY 1",
            "SELECT c.region, AVG(CASE WHEN l.status='default' THEN 1.0 ELSE 0.0 END) "
            "FROM loans l JOIN customers c ON l.customer_id=c.customer_id GROUP BY 1",
            "SELECT c.segment, AVG(l.principal), "
            "AVG(CASE WHEN l.status='default' THEN 1.0 ELSE 0.0 END) "
            "FROM loans l JOIN customers c ON l.customer_id=c.customer_id GROUP BY 1",
            "SELECT EXTRACT(MONTH FROM txn_date) AS m, category, SUM(amount) "
            "FROM transactions GROUP BY 1,2 ORDER BY 1",
            "SELECT a.status, AVG(EXTRACT(YEAR FROM c.join_date)) "
            "FROM accounts a JOIN customers c ON a.customer_id=c.customer_id "
            "GROUP BY 1",
        ],
        intermediate=[],
        final_output=LEVEL4_RESPONSE,
        token_count=1500,
        duration_ms=20000,
        errors=[],
    )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_level4_grading(
    rubrics_path: Path,
    eval_db: str,
    llm_judge: LLMJudge,
    level4_trace: AgentTrace,
) -> None:
    """Verify Level 4 grading pipeline produces a non-F result."""
    rubric = load_rubric(rubrics_path / "level4_free_explore.yaml")

    checks = {
        "discovery_quality": [
            lambda t: "credit score" in t.final_output.lower()
            and "default" in t.final_output.lower(),
        ],
    }

    result = await evaluate_level(rubric, level4_trace, llm_judge, checks)
    print("\n" + format_level_result(result))
    for d in result.dimensions:
        print(f"  {d.name}: {d.grade} — {d.justification}")
    assert result.grade != "F", f"Level 4 failed: score={result.weighted_score:.2f}"
