from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    (home / "inbox").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_cli_habits_learn_writes_proposal(sb_home: Path):
    lines = []
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    for i in range(3):
        lines.append(f"- {ts} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml")
        lines.append("  prior: papers")
    (sb_home / "log.md").write_text("\n".join(lines) + "\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["habits", "learn", "--threshold", "3"])
    assert result.exit_code == 0, result.output
    assert "1 proposal" in result.output or "proposals:" in result.output.lower()
    assert list((sb_home / "proposals").glob("habits-*.md"))


def test_cli_habits_learn_empty_when_below_threshold(sb_home: Path):
    (sb_home / "log.md").write_text("")
    runner = CliRunner()
    result = runner.invoke(cli, ["habits", "learn"])
    assert result.exit_code == 0
    assert "no proposals" in result.output.lower()


def test_cli_analytics_rebuild(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["analytics", "rebuild"])
    assert result.exit_code == 0, result.output
    assert (sb_home / ".sb" / "analytics.duckdb").exists()


def test_cli_analytics_rebuild_is_idempotent(sb_home: Path):
    runner = CliRunner()
    assert runner.invoke(cli, ["analytics", "rebuild"]).exit_code == 0
    # Second run must succeed too and leave the DB intact.
    result = runner.invoke(cli, ["analytics", "rebuild"])
    assert result.exit_code == 0, result.output
    assert (sb_home / ".sb" / "analytics.duckdb").exists()


def test_cli_stats_text(sb_home: Path):
    from second_brain.analytics.builder import AnalyticsBuilder
    from second_brain.config import Config

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()

    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0, result.output
    assert "health" in result.output.lower()
    assert "sources" in result.output.lower()


def test_cli_stats_json(sb_home: Path):
    from second_brain.analytics.builder import AnalyticsBuilder
    from second_brain.config import Config

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()

    runner = CliRunner()
    result = runner.invoke(cli, ["stats", "--json"])
    assert result.exit_code == 0
    import json as _json

    payload = _json.loads(result.output)
    assert "health" in payload
    assert "score" in payload["health"]
    assert "stats" in payload


def test_cli_eval_runs_all_suites(sb_home: Path):
    runner = CliRunner()
    fixtures = Path(__file__).parent / "eval" / "fixtures"
    result = runner.invoke(
        cli, ["eval", "--fixtures-dir", str(fixtures)]
    )
    assert result.exit_code == 0, result.output
    assert "retrieval" in result.output
    assert "graph" in result.output
    assert "ingest" in result.output


def test_cli_eval_single_suite(sb_home: Path):
    runner = CliRunner()
    fixtures = Path(__file__).parent / "eval" / "fixtures"
    result = runner.invoke(
        cli, ["eval", "--suite", "retrieval", "--fixtures-dir", str(fixtures)]
    )
    assert result.exit_code == 0
    assert "retrieval" in result.output
    assert "graph" not in result.output
