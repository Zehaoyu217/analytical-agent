from __future__ import annotations

from second_brain.stats.collector import Stats
from second_brain.stats.health import HealthWeights, compute_health


def test_perfect_kb_scores_100():
    s = Stats(
        source_count=10,
        claim_count=30,
        inbox_pending=0,
        zero_claim_sources=0,
        orphan_claims=0,
        open_contradictions=0,
        resolved_contradictions=0,
        auto_reverts_7d=0,
        open_contradictions_older_than_7d=0,
    )
    h = compute_health(s)
    assert h.score == 100
    assert h.breakdown


def test_score_drops_for_orphans_and_zero_claims():
    s = Stats(
        source_count=10,
        claim_count=30,
        inbox_pending=0,
        zero_claim_sources=5,
        orphan_claims=10,
        open_contradictions=0,
        resolved_contradictions=0,
        auto_reverts_7d=0,
        open_contradictions_older_than_7d=0,
    )
    h = compute_health(s)
    assert h.score < 100
    assert "zero_claim_sources" in h.breakdown


def test_score_clamped_at_zero():
    s = Stats(
        source_count=10,
        claim_count=30,
        inbox_pending=0,
        zero_claim_sources=100,
        orphan_claims=100,
        open_contradictions=100,
        resolved_contradictions=0,
        auto_reverts_7d=100,
        open_contradictions_older_than_7d=100,
    )
    h = compute_health(s)
    assert 0 <= h.score <= 100


def test_resolved_contradictions_is_positive_signal():
    s_no_resolved = Stats(
        source_count=10,
        claim_count=30,
        inbox_pending=0,
        zero_claim_sources=0,
        orphan_claims=0,
        open_contradictions=5,
        resolved_contradictions=0,
        auto_reverts_7d=0,
        open_contradictions_older_than_7d=0,
    )
    s_with_resolved = Stats(
        source_count=10,
        claim_count=30,
        inbox_pending=0,
        zero_claim_sources=0,
        orphan_claims=0,
        open_contradictions=5,
        resolved_contradictions=10,
        auto_reverts_7d=0,
        open_contradictions_older_than_7d=0,
    )
    assert (
        compute_health(s_with_resolved).score >= compute_health(s_no_resolved).score
    )


def test_weights_override_changes_score():
    s = Stats(
        source_count=10,
        claim_count=30,
        inbox_pending=0,
        zero_claim_sources=5,
        orphan_claims=0,
        open_contradictions=0,
        resolved_contradictions=0,
        auto_reverts_7d=0,
        open_contradictions_older_than_7d=0,
    )
    default = compute_health(s)
    stricter = compute_health(s, HealthWeights(zero_claim_source=5))
    assert stricter.score < default.score
