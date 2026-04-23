"""Tests for the digest_unread_penalty signal in sb stats health score."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.stats.collector import Stats, collect_stats
from second_brain.stats.health import compute_health


def _write_digest(digests: Path, d: date, body: str = "# digest\n") -> None:
    digests.mkdir(parents=True, exist_ok=True)
    (digests / f"{d.isoformat()}.md").write_text(body)


def test_collect_stats_counts_unread_stale_digests(sb_home: Path) -> None:
    cfg = Config.load()
    today = date.today()
    digests = cfg.digests_dir
    # 2 stale unread (>3 days old, not marked)
    _write_digest(digests, today - timedelta(days=4))
    _write_digest(digests, today - timedelta(days=10))
    # 1 fresh (within 3 days) — should not count
    _write_digest(digests, today - timedelta(days=1))
    # 1 stale but marked read — should not count
    stale_read = today - timedelta(days=7)
    _write_digest(digests, stale_read)
    (digests / ".read_marks").write_text(f"{stale_read.isoformat()}\n")

    stats = collect_stats(cfg)
    assert stats.unread_stale_digests == 2


def test_health_applies_digest_unread_penalty() -> None:
    s = Stats(unread_stale_digests=2)
    h = compute_health(s)
    assert h.breakdown["digest_unread_penalty"] == -4
    assert h.breakdown["unread_digest_count"] == 2
    assert h.score == 100 - 4


def test_health_caps_digest_unread_penalty() -> None:
    # 20 unread stale at -2 each would be -40; cap at -10
    s = Stats(unread_stale_digests=20)
    h = compute_health(s)
    assert h.breakdown["digest_unread_penalty"] == -10
    assert h.breakdown["unread_digest_count"] == 20


def test_health_no_digest_penalty_when_clean() -> None:
    s = Stats(unread_stale_digests=0)
    h = compute_health(s)
    assert h.breakdown["digest_unread_penalty"] == 0
    assert h.breakdown["unread_digest_count"] == 0
    assert h.score == 100
