"""Health score (0-100, higher is better).

Score starts at 100 and subtracts capped penalties for problems; adds a small
bonus for resolved/open contradiction ratio as a positive signal. Clamped to
[0, 100]. Weights are tunable via :class:`HealthWeights`.

Default penalties (see ``HealthWeights``):

- zero-claim sources: -2 each, capped at -30
- orphan claims: -1 each, capped at -20
- open contradictions older than 7 days: -3 each, capped at -20
- auto decisions reverted in the last 7 days: -5 each, capped at -15

Positive signal:

- resolved/open contradiction ratio * 5, capped at +5
"""
from __future__ import annotations

from dataclasses import dataclass, field

from second_brain.stats.collector import Stats


@dataclass(frozen=True)
class HealthWeights:
    zero_claim_source: int = 2
    zero_claim_cap: int = 30
    orphan_claim: int = 1
    orphan_cap: int = 20
    stale_contradiction: int = 3
    stale_contradiction_cap: int = 20
    auto_revert: int = 5
    auto_revert_cap: int = 15
    resolved_ratio_bonus_cap: int = 5
    digest_unread: int = 2
    digest_unread_cap: int = 10


@dataclass(frozen=True)
class HealthScore:
    score: int
    breakdown: dict[str, int] = field(default_factory=dict)


def compute_health(
    stats: Stats, weights: HealthWeights | None = None
) -> HealthScore:
    """Compute a 0-100 health score from a :class:`Stats` snapshot.

    The breakdown dict reports the signed contribution of each component
    (negative for penalties, positive for bonuses) so callers can surface
    exactly which signals drove the score.
    """
    w = weights or HealthWeights()
    breakdown: dict[str, int] = {}

    zc = min(w.zero_claim_cap, stats.zero_claim_sources * w.zero_claim_source)
    breakdown["zero_claim_sources"] = -zc

    oc = min(w.orphan_cap, stats.orphan_claims * w.orphan_claim)
    breakdown["orphan_claims"] = -oc

    sc = min(
        w.stale_contradiction_cap,
        stats.open_contradictions_older_than_7d * w.stale_contradiction,
    )
    breakdown["stale_contradictions"] = -sc

    ar = min(w.auto_revert_cap, stats.auto_reverts_7d * w.auto_revert)
    breakdown["auto_reverts_7d"] = -ar

    ratio_bonus = 0
    if stats.open_contradictions > 0:
        ratio = stats.resolved_contradictions / stats.open_contradictions
        ratio_bonus = min(
            w.resolved_ratio_bonus_cap, int(ratio * w.resolved_ratio_bonus_cap)
        )
    breakdown["resolved_ratio_bonus"] = ratio_bonus

    du = min(w.digest_unread_cap, stats.unread_stale_digests * w.digest_unread)
    breakdown["digest_unread_penalty"] = -du
    breakdown["unread_digest_count"] = stats.unread_stale_digests

    score = 100 - zc - oc - sc - ar - du + ratio_bonus
    score = max(0, min(100, score))
    return HealthScore(score=score, breakdown=breakdown)
