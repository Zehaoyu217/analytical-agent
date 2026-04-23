from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.analytics.builder import AnalyticsBuilder
from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.stats.collector import Stats, collect_stats


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    (home / "inbox").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_collect_stats_empty_kb(sb_home: Path):
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    s = collect_stats(cfg)
    assert isinstance(s, Stats)
    assert s.source_count == 0
    assert s.claim_count == 0
    assert s.inbox_pending == 0


def test_collect_stats_counts(sb_home: Path):
    for i in range(3):
        folder = sb_home / "sources" / f"src_{i}"
        folder.mkdir()
        dump_document(
            folder / "_source.md",
            {
                "id": f"src_{i}",
                "title": "t",
                "kind": "note",
                "content_hash": f"h{i}",
                "raw": [],
                "ingested_at": "2026-04-18T00:00:00Z",
            },
            "",
        )
    (sb_home / "inbox" / "pending.md").write_text("x")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    s = collect_stats(cfg)
    assert s.source_count == 3
    assert s.inbox_pending == 1
