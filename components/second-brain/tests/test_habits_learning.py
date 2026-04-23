from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.habits.learning import (
    HabitProposal,
    detect_overrides,
    write_proposal,
)


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _write_log(home: Path, lines: list[str]) -> None:
    (home / "log.md").write_text("\n".join(lines) + "\n")


def _now_iso(delta_days: int = 0) -> str:
    ts = datetime.now(UTC) - timedelta(days=delta_days)
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def test_detect_override_fires_at_threshold_three(sb_home: Path):
    lines = []
    for i in range(3):
        lines.append(
            f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml/transformers"
        )
        lines.append("  prior: papers/ml")
    _write_log(sb_home, lines)

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)

    assert len(proposals) == 1
    p = proposals[0]
    assert p.op == "ingest.taxonomy"
    assert "papers/ml/transformers" in p.proposed_value
    assert len(p.sample_subjects) == 3
    assert p.count >= 3


def test_detect_ignores_overrides_outside_window(sb_home: Path):
    lines = []
    for i in range(3):
        lines.append(
            f"- {_now_iso(90 + i)} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml"
        )
        lines.append("  prior: papers")
    _write_log(sb_home, lines)

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)
    assert proposals == []


def test_detect_below_threshold_returns_empty(sb_home: Path):
    lines = [
        f"- {_now_iso(0)} [USER_OVERRIDE] ingest.taxonomy src_a → papers/ml",
        "  prior: papers",
        f"- {_now_iso(1)} [USER_OVERRIDE] ingest.taxonomy src_b → papers/ml",
        "  prior: papers",
    ]
    _write_log(sb_home, lines)
    cfg = Config.load()
    assert detect_overrides(cfg, window_days=60, threshold=3) == []


def test_detect_groups_by_op_and_value(sb_home: Path):
    lines = []
    for i in range(3):
        lines.append(f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_a{i} → A/B")
        lines.append("  prior: A")
        lines.append(f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_b{i} → X/Y")
        lines.append("  prior: X")
    _write_log(sb_home, lines)
    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)
    assert len(proposals) == 2
    values = sorted(p.proposed_value for p in proposals)
    assert values == ["A/B", "X/Y"]


def test_write_proposal_creates_markdown(sb_home: Path):
    cfg = Config.load()
    prop = HabitProposal(
        op="ingest.taxonomy",
        proposed_value="papers/ml/transformers",
        prior_value="papers/ml",
        count=3,
        sample_subjects=["src_a", "src_b", "src_c"],
    )
    path = write_proposal(prop, cfg)
    text = path.read_text()
    assert path.parent == cfg.proposals_dir
    assert "ingest.taxonomy" in text
    assert "papers/ml/transformers" in text
    assert "src_a" in text


def test_detect_no_log_file_returns_empty(sb_home: Path):
    cfg = Config.load()
    # No log.md written; detection should degrade gracefully
    assert detect_overrides(cfg, window_days=60, threshold=3) == []


def test_detect_handles_missing_prior_line(sb_home: Path):
    # USER_OVERRIDE lines without following prior: lines must still be counted.
    lines = []
    for i in range(3):
        lines.append(
            f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_q{i} → papers/ml/gpt"
        )
    _write_log(sb_home, lines)

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)
    assert len(proposals) == 1
    assert proposals[0].count == 3
    assert proposals[0].prior_value is None
