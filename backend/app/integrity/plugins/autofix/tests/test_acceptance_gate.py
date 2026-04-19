"""Gate ζ acceptance test — 5 fix classes produce diff plans against synthetic
fixture, no git side effects."""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.integrity.plugins.autofix.plugin import AutofixPlugin
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _seed_repo(repo: Path) -> None:
    """Create the minimum repo state needed for all 5 fixers to find work."""
    (repo / "graphify").mkdir()
    (repo / "graphify" / "graph.json").write_text('{"nodes":[],"links":[]}')
    (repo / "graphify" / "graph.augmented.json").write_text('{"nodes":[],"links":[]}')

    # claude_md_link — CLAUDE.md exists; docs/new-guide.md unindexed.
    (repo / "CLAUDE.md").write_text("# Project\n\n## Deeper Context\n\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "new-guide.md").write_text("# New Guide\n")

    # doc_link_renamed — docs/landing.md has a broken link.
    (repo / "docs" / "landing.md").write_text(
        "see [legacy](docs/old/legacy.md) for context\n"
    )

    # manifest_regen — drifted manifest.
    (repo / "config").mkdir()
    (repo / "config" / "manifest.yaml").write_text("inputs: []\n")

    # dead_directive_cleanup — file with dead noqa.
    (repo / "src").mkdir()
    (repo / "src" / "dead.py").write_text("import os  # noqa: F401\n")

    # health_dashboard_refresh — dashboards exist with stale content.
    (repo / "docs" / "health").mkdir()
    (repo / "docs" / "health" / "latest.md").write_text("# stale\n")
    (repo / "docs" / "health" / "trend.md").write_text("# stale\n")


def _seed_artifacts(repo: Path, today: date) -> None:
    out = repo / "integrity-out" / today.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES_DIR / "doc_audit_unindexed.json", out / "doc_audit.json")
    shutil.copy(FIXTURES_DIR / "config_registry_drift.json", out / "config_registry.json")
    shutil.copy(FIXTURES_DIR / "graph_lint_dead_directive.json", out / "graph_lint.json")
    shutil.copy(FIXTURES_DIR / "report_aggregate.json", out / "report.json")


def test_acceptance_5_fixers_produce_dry_run_diffs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)
    today = date(2026, 4, 17)
    _seed_artifacts(repo, today)

    # Mock git log for doc_link_renamed and Plugin E's emitter for manifest_regen.
    git_log_out = "abc\n--- a/docs/old/legacy.md\n+++ b/docs/legacy.md\n"

    def fake_subprocess(*args, **kwargs):
        from subprocess import CompletedProcess
        argv = args[0] if args else kwargs.get("args", [])
        if argv and argv[0] == "git" and "log" in argv:
            return CompletedProcess(args=argv, returncode=0, stdout=git_log_out, stderr="")
        return CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess), \
         patch(
             "backend.app.integrity.plugins.autofix.fixers.manifest_regen._regenerate_manifest_text",
             return_value="inputs:\n  - scripts/new-script.sh\n",
         ):
        plugin = AutofixPlugin(today=today, apply=False)
        graph = GraphSnapshot.load(repo)
        plugin.scan(ScanContext(repo_root=repo, graph=graph))

    artifact = repo / "integrity-out" / today.isoformat() / "autofix.json"
    payload = json.loads(artifact.read_text())

    assert payload["mode"] == "dry-run"

    # All 5 fix classes ran (none disabled, none erroring, all produced diffs).
    expected = {
        "claude_md_link", "doc_link_renamed", "manifest_regen",
        "dead_directive_cleanup", "health_dashboard_refresh",
    }
    assert set(payload["fix_classes_run"]) == expected

    # Each class has at least one non-noop diff.
    for fc in expected:
        assert len(payload["diffs_by_class"][fc]) >= 1, (
            f"{fc}: expected ≥1 diff, got {payload['diffs_by_class'][fc]!r}"
        )

    # No git side effects: no autofix branches created (we mocked subprocess).
    # The dispatcher is not invoked in dry-run, so subprocess.run shouldn't be
    # called for git checkout/commit/push.
    assert payload["pr_results"] == {}

    # No ERROR-severity issues.
    errs = [i for i in payload["issues"] if i["severity"] == "ERROR"]
    assert errs == [], f"unexpected ERROR issues: {errs}"
