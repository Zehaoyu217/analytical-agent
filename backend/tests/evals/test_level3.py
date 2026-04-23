"""Level 3: Anomaly Detection + False Positive Screening.

Requires the local MLX judge model for LLM-judged dimensions.
Run: cd backend && python -m pytest tests/evals/test_level3.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.judge import LLMJudge
from app.evals.rubric import load_rubric
from app.evals.runner import evaluate_level, format_level_result
from app.evals.types import AgentTrace

LEVEL3_RESPONSE = """\
## Anomaly Detection Report — Q3 2025

### Methodology
Applied z-score analysis (threshold > 3.0) on transaction amounts per account, \
followed by frequency analysis for burst patterns. Then manually reviewed raw \
data for each flagged group.

### Flagged Anomaly Groups

#### A1: Large Wire Transfer — CONFIRMED ANOMALY
- Account status: dormant (no activity for months)
- Transaction: $47,000 wire to "Unknown Entity LLC" on 2025-07-14
- Risk: Dormant account suddenly executing a large wire transfer to an unknown \
entity is a strong indicator of compromised credentials.
- **Classification: TRUE ANOMALY — stolen credentials**

#### A2: ATM Withdrawal Burst — CONFIRMED ANOMALY
- 12 ATM withdrawals on 2025-08-03 totaling ~$4,200
- Locations: New York, Chicago, Miami (3 different cities)
- Timing: All within the same day — physically impossible
- **Classification: TRUE ANOMALY — card cloning**

#### A3: Shell Company Transfers — CONFIRMED ANOMALY
- 4 transfers to "Oceanic Holdings Ltd" between Aug 10 - Aug 31
- Total: ~$38,000
- This counterparty has no prior transaction history
- Regular weekly cadence suggests automated transfers
- **Classification: TRUE ANOMALY — suspicious new counterparty**

#### A4: $15,000 Deposit — DISMISSED (False Positive)
- Deposit from "Acme Corporation" labeled "Annual Performance Bonus 2025"
- Category: payroll — consistent with employer deposits
- Amount is within expected range for annual bonuses
- **Classification: FALSE POSITIVE — annual bonus deposit**

#### A5: $50,000 Transfer — DISMISSED (False Positive)
- Internal transfer labeled "Transfer from savings — home purchase down payment"
- Counterparty: "Self — savings closure"
- This is a customer moving their own money between accounts
- **Classification: FALSE POSITIVE — planned savings withdrawal for home purchase**

#### A6: Weekend Merchant Charges — DISMISSED (False Positive)
- 8 charges on 2025-09-06 (Saturday) totaling ~$480
- Merchants: Target, Whole Foods, Home Depot, Starbucks, Best Buy, CVS, \
Trader Joe's, Shell Gas
- All are common retail stores, small amounts ($8-$120)
- **Classification: FALSE POSITIVE — normal weekend shopping trip**

### Summary
| ID | Type | Decision | Confidence |
|----|------|----------|------------|
| A1 | Wire from dormant | CONFIRMED | High |
| A2 | ATM burst | CONFIRMED | High |
| A3 | Shell company | CONFIRMED | High |
| A4 | Large deposit | DISMISSED | High |
| A5 | Large transfer | DISMISSED | High |
| A6 | Weekend charges | DISMISSED | Medium |

**3 confirmed anomalies, 3 false positives dismissed.**

### Recommended Actions
1. A1: Freeze account, investigate credentials breach
2. A2: Block card, issue replacement, file fraud report
3. A3: Flag for compliance review, possible SAR filing\
"""


@pytest.fixture
def level3_trace() -> AgentTrace:
    return AgentTrace(
        queries=[
            "SELECT account_id, amount, txn_date, category, counterparty "
            "FROM transactions WHERE txn_date >= '2025-07-01' AND txn_date < '2025-10-01' "
            "ORDER BY ABS(amount) DESC LIMIT 50",
            "SELECT account_id, COUNT(*) AS cnt, SUM(amount) AS total "
            "FROM transactions WHERE txn_date >= '2025-07-01' AND txn_date < '2025-10-01' "
            "GROUP BY account_id HAVING COUNT(*) > 10",
            "SELECT t.*, a.status FROM transactions t "
            "JOIN accounts a ON t.account_id = a.account_id "
            "WHERE t.is_flagged ORDER BY t.txn_date",
            "SELECT counterparty, COUNT(*) FROM transactions "
            "WHERE txn_date < '2025-07-01' AND counterparty = 'Oceanic Holdings Ltd'",
        ],
        intermediate=[],
        final_output=LEVEL3_RESPONSE,
        token_count=1200,
        duration_ms=15000,
        errors=[],
    )


def _check_detects_true_anomalies(trace: AgentTrace) -> bool:
    output = trace.final_output.lower()
    return (
        "a1" in output and "confirmed" in output
        and "a2" in output
        and "a3" in output
    )


def _check_dismisses_false_positives(trace: AgentTrace) -> bool:
    output = trace.final_output.lower()
    return (
        "a4" in output and "false positive" in output
        and "a5" in output
        and "a6" in output and "dismissed" in output
    )


@pytest.mark.asyncio
async def test_level3_grading(
    rubrics_path: Path,
    eval_db: str,
    llm_judge: LLMJudge,
    level3_trace: AgentTrace,
) -> None:
    """Verify Level 3 grading pipeline produces a non-F result."""
    rubric = load_rubric(rubrics_path / "level3_anomaly.yaml")

    checks = {
        "detection_recall": [
            _check_detects_true_anomalies,
            lambda t: "wire" in t.final_output.lower(),
            lambda t: "atm" in t.final_output.lower(),
            lambda t: "oceanic" in t.final_output.lower(),
        ],
        "false_positive_handling": [
            _check_dismisses_false_positives,
            lambda t: "bonus" in t.final_output.lower(),
            lambda t: "shopping" in t.final_output.lower()
            or "weekend" in t.final_output.lower(),
        ],
    }

    result = await evaluate_level(rubric, level3_trace, llm_judge, checks)
    print("\n" + format_level_result(result))
    for d in result.dimensions:
        print(f"  {d.name}: {d.grade} — {d.justification}")
    assert result.grade != "F", f"Level 3 failed: score={result.weighted_score:.2f}"
