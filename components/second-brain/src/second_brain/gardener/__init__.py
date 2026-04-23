"""Gardener — autonomous LLM knowledge maintenance.

Ships as a 4th pipeline phase alongside ingest/digest/maintain. Runs
opt-in LLM passes that write proposals into ``digests/pending.jsonl`` for
the existing Digest flow to emit. Proposal-only by default; autonomous
mode lets passes write directly (with full audit).
"""
from second_brain.gardener.protocol import (
    Budget,
    BudgetExceeded,
    CostEstimate,
    GardenerPass,
    Proposal,
    RunResult,
)

__all__ = [
    "Budget",
    "BudgetExceeded",
    "CostEstimate",
    "GardenerPass",
    "Proposal",
    "RunResult",
]
