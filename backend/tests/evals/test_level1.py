"""Level 1: Basic Rendering — chart, table, and mermaid ERD.

Requires the local MLX judge model for LLM-judged dimensions.
Run: cd backend && python -m pytest tests/evals/test_level1.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import LLMJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level, format_level_result
from app.evals.types import AgentTrace

LEVEL1_RESPONSE = """\
## Monthly Transaction Volume and Amount — 2025

| Month | Volume | Total Amount |
|-------|--------|-------------|
| January | 425 | $1,234,567.89 |
| February | 398 | $1,189,234.56 |
| March | 445 | $1,345,678.90 |
| April | 410 | $1,267,890.12 |
| May | 432 | $1,298,456.78 |
| June | 418 | $1,256,789.01 |
| July | 467 | $1,456,789.23 |
| August | 455 | $1,423,456.78 |
| September | 440 | $1,378,901.23 |
| October | 430 | $1,312,345.67 |
| November | 458 | $1,445,678.90 |
| December | 472 | $1,512,345.67 |

[Bar chart rendered with labeled axes]

## Top 10 Customers by Total Deposits

| Rank | Customer | Total Deposits |
|------|----------|---------------|
| 1 | James Wilson | $234,567.89 |
| 2 | Sarah Johnson | $198,456.78 |
| 3 | Michael Chen | $187,234.56 |
| 4 | Emily Rodriguez | $176,890.12 |
| 5 | David Kim | $165,678.90 |
| 6 | Lisa Thompson | $154,321.09 |
| 7 | Robert Davis | $143,567.89 |
| 8 | Jennifer Martinez | $132,890.45 |
| 9 | William Brown | $121,456.78 |
| 10 | Amanda Taylor | $110,234.56 |

## Entity Relationship Diagram

```mermaid
erDiagram
    customers ||--o{ accounts : has
    customers ||--o{ loans : has
    accounts ||--o{ transactions : contains
    customers {
        int customer_id PK
        varchar name
        varchar segment
    }
    accounts {
        int account_id PK
        int customer_id FK
    }
    transactions {
        int txn_id PK
        int account_id FK
    }
    loans {
        int loan_id PK
        int customer_id FK
    }
    daily_rates {
        date rate_date PK
    }
```\
"""


@pytest.fixture
def level1_trace() -> AgentTrace:
    return AgentTrace(
        queries=[
            "SELECT DATE_TRUNC('month', txn_date) AS month, COUNT(*) AS volume, "
            "SUM(amount) AS total FROM transactions WHERE txn_date >= '2025-01-01' "
            "GROUP BY 1 ORDER BY 1",
            "SELECT c.name, SUM(t.amount) AS total_deposits FROM customers c "
            "JOIN accounts a ON c.customer_id = a.customer_id "
            "JOIN transactions t ON a.account_id = t.account_id "
            "WHERE t.amount > 0 GROUP BY c.name ORDER BY total_deposits DESC LIMIT 10",
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'main'",
        ],
        intermediate=[],
        final_output=LEVEL1_RESPONSE,
        token_count=800,
        duration_ms=5000,
        errors=[],
    )


@pytest.mark.asyncio
async def test_level1_grading(
    rubrics_path: Path,
    eval_db: str,
    llm_judge: LLMJudge,
    level1_trace: AgentTrace,
) -> None:
    """Verify Level 1 grading pipeline produces a non-F result."""
    rubric = load_rubric(rubrics_path / "level1_rendering.yaml")

    checks = {
        "table_correctness": [
            lambda t: t.final_output.count("$") >= 10,
            lambda t: "Top 10" in t.final_output,
        ],
        "mermaid_erd": [
            lambda t: "```mermaid" in t.final_output,
            lambda t: "erDiagram" in t.final_output,
            lambda t: all(
                name in t.final_output
                for name in [
                    "customers", "accounts", "transactions",
                    "loans", "daily_rates",
                ]
            ),
        ],
    }

    result = await evaluate_level(rubric, level1_trace, llm_judge, checks)
    print("\n" + format_level_result(result))
    for d in result.dimensions:
        print(f"  {d.name}: {d.grade} — {d.justification}")
    assert result.grade != "F", f"Level 1 failed: score={result.weighted_score:.2f}"
