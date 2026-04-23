from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.maintain.runner import MaintainRunner


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _claim(home: Path, slug: str, *, abstract: str, body: str) -> None:
    folder = home / "claims"
    folder.mkdir(exist_ok=True)
    dump_document(
        folder / f"{slug}.md",
        {
            "id": slug,
            "statement": slug,
            "kind": "empirical",
            "confidence": "low",
            "extracted_at": "2026-04-18T00:00:00Z",
            "abstract": abstract,
        },
        body,
    )


def test_maintain_runner_returns_report_with_counts(sb_home: Path):
    _claim(sb_home, "clm_a", abstract="", body="x" * 500)  # stale
    _claim(sb_home, "clm_b", abstract="summary", body="x" * 500)  # not stale
    cfg = Config.load()

    report = MaintainRunner(cfg).run()

    assert "clm_a" in report.stale_abstracts
    assert "clm_b" not in report.stale_abstracts
    assert report.lint_counts is not None
    assert report.open_contradictions >= 0


def test_maintain_runner_emits_log_entry(sb_home: Path):
    cfg = Config.load()
    MaintainRunner(cfg).run()
    log = (sb_home / "log.md").read_text()
    assert "[MAINTAIN]" in log


def test_maintain_rebuilds_analytics_and_runs_learning(sb_home: Path):
    # Seed 3 USER_OVERRIDE entries so the learner fires a proposal.
    from datetime import UTC, datetime

    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    lines = []
    for i in range(3):
        lines.append(f"- {ts} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml")
        lines.append("  prior: papers")
    (sb_home / "log.md").write_text("\n".join(lines) + "\n")

    cfg = Config.load()
    report = MaintainRunner(cfg).run()

    assert (sb_home / ".sb" / "analytics.duckdb").exists()
    assert report.analytics_rebuilt is True
    assert report.habit_proposals >= 1
