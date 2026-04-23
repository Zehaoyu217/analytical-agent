"""Core types for the gardener runtime.

Defines the ``GardenerPass`` protocol, ``Proposal`` shape (compatible with
the existing ``DigestEntry.action`` payload), ``Budget`` enforcement, and
``CostEstimate`` for pre-flight UI previews.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Protocol, runtime_checkable

Tier = Literal["cheap", "default", "deep"]


class BudgetExceeded(Exception):
    """Raised when cumulative cost exceeds the configured cap."""


@dataclass(frozen=True)
class Proposal:
    """One proposed action emitted by a gardener pass.

    Shape intentionally mirrors ``DigestEntry`` so the digest pipeline can
    merge proposals without translation.
    """

    pass_name: str
    section: str
    line: str
    action: dict[str, Any]
    input_refs: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    origin: str = "gardener"


@dataclass(frozen=True)
class PassEstimate:
    tokens: int
    cost_usd: float


@dataclass(frozen=True)
class CostEstimate:
    passes: dict[str, PassEstimate] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(p.tokens for p in self.passes.values())

    @property
    def total_cost_usd(self) -> float:
        return sum(p.cost_usd for p in self.passes.values())


@dataclass
class Budget:
    """Mutable budget tracker; raises ``BudgetExceeded`` when tripped."""

    max_cost_usd_per_run: float
    max_tokens_per_source: int
    spent_usd: float = 0.0
    tokens_spent: int = 0

    def charge(self, cost_usd: float, tokens: int = 0) -> None:
        self.spent_usd += cost_usd
        self.tokens_spent += tokens
        if self.spent_usd > self.max_cost_usd_per_run:
            raise BudgetExceeded(
                f"run cost ${self.spent_usd:.4f} exceeds cap "
                f"${self.max_cost_usd_per_run:.4f}"
            )

    def remaining_usd(self) -> float:
        return max(0.0, self.max_cost_usd_per_run - self.spent_usd)


@dataclass(frozen=True)
class RunResult:
    passes_run: list[str]
    proposals_added: int
    total_tokens: int
    total_cost_usd: float
    duration_ms: int
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class GardenerPass(Protocol):
    """Stateless pass contract. Each pass is a single-purpose module."""

    name: str
    tier: Tier
    prefix: str  # pending.jsonl id prefix, e.g. "gx" for gardener-extract

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate: ...

    def run(
        self, cfg: Any, habits: Any, client: Any, budget: Budget
    ) -> Iterator[Proposal]: ...
