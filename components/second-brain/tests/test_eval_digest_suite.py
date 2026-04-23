"""Tests for the `sb eval digest` suite: per-pass golden comparison."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.eval.suites.digest import (
    PASS_NAMES,
    default_fixtures_dir,
    run_digest_suite,
)


def test_all_five_passes_match_golden() -> None:
    outcomes = run_digest_suite()
    names = {o.pass_name for o in outcomes}
    assert names == set(PASS_NAMES)
    for o in outcomes:
        assert o.passed, (
            f"{o.pass_name}: generated={o.generated} expected={o.expected} "
            f"tp={o.true_positives}"
        )


def test_single_pass_filter() -> None:
    outcomes = run_digest_suite(pass_filter="edge_audit")
    assert len(outcomes) == 1
    assert outcomes[0].pass_name == "edge_audit"
    assert outcomes[0].passed


def test_fixtures_dir_ships_with_package() -> None:
    fixtures = default_fixtures_dir()
    assert fixtures.is_dir()
    for name in PASS_NAMES:
        assert (fixtures / name / "input.yaml").exists()
        assert (fixtures / name / "expected.yaml").exists()


def test_cli_eval_digest_default_runs_all(sb_home: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", "digest"])
    assert result.exit_code == 0, result.output
    for name in PASS_NAMES:
        assert name in result.output


def test_cli_eval_digest_filter(sb_home: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", "digest", "--pass", "wiki_bridge"])
    assert result.exit_code == 0, result.output
    assert "wiki_bridge" in result.output
    assert "reconciliation" not in result.output


def test_cli_eval_digest_json(sb_home: Path) -> None:
    import json as _json

    runner = CliRunner()
    result = runner.invoke(cli, ["eval", "digest", "--json"])
    assert result.exit_code == 0, result.output
    data = _json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == len(PASS_NAMES)
    first = data[0]
    assert {"pass", "generated", "expected", "true_positives", "precision", "recall", "passed"} <= set(first)
