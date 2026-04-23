"""Collect derived KB statistics for dashboards + health scoring.

Reads from ``.sb/analytics.duckdb`` (populated by ``AnalyticsBuilder``) plus
inbox scan. All missing inputs degrade gracefully to zeros so the function is
safe to call on a fresh or partially-initialized KB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from second_brain.analytics.queries import (
    claims_by_taxonomy,
    contradiction_counts,
    orphan_claims,
    sources_by_kind,
    zero_claim_sources,
)
from second_brain.config import Config

_DIGEST_STALE_DAYS = 3


@dataclass(frozen=True)
class Stats:
    source_count: int = 0
    claim_count: int = 0
    inbox_pending: int = 0
    zero_claim_sources: int = 0
    orphan_claims: int = 0
    open_contradictions: int = 0
    resolved_contradictions: int = 0
    open_contradictions_older_than_7d: int = 0
    auto_reverts_7d: int = 0
    sources_by_kind: dict[str, int] = field(default_factory=dict)
    claims_by_taxonomy: dict[str, int] = field(default_factory=dict)
    unread_stale_digests: int = 0


def _count_inbox_pending(cfg: Config) -> int:
    if not cfg.inbox_dir.exists():
        return 0
    return sum(
        1
        for p in cfg.inbox_dir.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )


def _count_unread_stale_digests(cfg: Config, today: date | None = None) -> int:
    """Count digest markdown files older than ``_DIGEST_STALE_DAYS`` whose date
    is not present in ``digests/.read_marks``.

    A digest is identified by its filename stem being a valid ISO date. Files
    that fail the date parse are ignored.
    """
    digests = cfg.digests_dir
    if not digests.exists():
        return 0
    today = today or date.today()
    cutoff = today - timedelta(days=_DIGEST_STALE_DAYS)
    marks_file = digests / ".read_marks"
    marked: set[str] = set()
    if marks_file.exists():
        marked = {
            line.strip()
            for line in marks_file.read_text().splitlines()
            if line.strip()
        }
    unread = 0
    for p in digests.glob("*.md"):
        try:
            d = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if d < cutoff and p.stem not in marked:
            unread += 1
    return unread


def collect_stats(cfg: Config) -> Stats:
    """Aggregate KB stats from the analytics DB + filesystem.

    Returns a :class:`Stats` snapshot. Safe to call when ``analytics.duckdb``
    is missing (all analytics-derived counters default to 0).
    """
    src_counts = dict(sources_by_kind(cfg))
    clm_counts = dict(claims_by_taxonomy(cfg))
    contradictions = dict(contradiction_counts(cfg))
    return Stats(
        source_count=sum(src_counts.values()),
        claim_count=sum(clm_counts.values()),
        inbox_pending=_count_inbox_pending(cfg),
        zero_claim_sources=len(list(zero_claim_sources(cfg))),
        orphan_claims=len(list(orphan_claims(cfg))),
        open_contradictions=int(contradictions.get("open", 0)),
        resolved_contradictions=int(contradictions.get("resolved", 0)),
        sources_by_kind=src_counts,
        claims_by_taxonomy=clm_counts,
        unread_stale_digests=_count_unread_stale_digests(cfg),
    )
