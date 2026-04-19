"""Integration tests for AutofixPlugin against the synthetic fixture."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.integrity.plugins.autofix.plugin import AutofixPlugin
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot


def _ctx(repo: Path) -> ScanContext:
    graph = GraphSnapshot.load(repo)
    return ScanContext(repo_root=repo, graph=graph)


def test_dry_run_writes_artifact_with_per_class_diffs(tiny_repo_with_artifacts: Path) -> None:
    repo = tiny_repo_with_artifacts
    plugin = AutofixPlugin(today=date(2026, 4, 17), apply=False)
    plugin.scan(_ctx(repo))

    artifact = repo / "integrity-out" / "2026-04-17" / "autofix.json"
    assert artifact.exists()
    payload = json.loads(artifact.read_text())
    assert payload["plugin"] == "autofix"
    assert payload["mode"] == "dry-run"
    assert "claude_md_link" in payload["diffs_by_class"]
    assert len(payload["diffs_by_class"]["claude_md_link"]) == 1


def test_emits_proposed_info_per_class(tiny_repo_with_artifacts: Path) -> None:
    repo = tiny_repo_with_artifacts
    plugin = AutofixPlugin(today=date(2026, 4, 17), apply=False)
    result = plugin.scan(_ctx(repo))
    proposed = [i for i in result.issues if i.rule == "autofix.proposed"]
    assert any(i.evidence.get("class") == "claude_md_link" for i in proposed)


def test_skips_when_upstream_artifact_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "graphify").mkdir()
    (repo / "graphify" / "graph.json").write_text('{"nodes":[],"links":[]}')
    (repo / "graphify" / "graph.augmented.json").write_text('{"nodes":[],"links":[]}')
    plugin = AutofixPlugin(today=date(2026, 4, 17), apply=False)
    result = plugin.scan(_ctx(repo))
    assert any(i.rule == "autofix.skipped_upstream_missing" for i in result.issues)
    artifact = repo / "integrity-out" / "2026-04-17" / "autofix.json"
    assert artifact.exists()
    payload = json.loads(artifact.read_text())
    assert payload["fix_classes_run"] == []


def test_apply_mode_requires_config_gate(tiny_repo_with_artifacts: Path) -> None:
    """`--apply` flag without `autofix.apply: true` config → still dry-run."""
    repo = tiny_repo_with_artifacts
    plugin = AutofixPlugin(today=date(2026, 4, 17), apply=True,
                           config={"apply": False})
    plugin.scan(_ctx(repo))
    artifact = repo / "integrity-out" / "2026-04-17" / "autofix.json"
    payload = json.loads(artifact.read_text())
    assert payload["mode"] == "dry-run"


def test_disabled_class_skipped(tiny_repo_with_artifacts: Path) -> None:
    repo = tiny_repo_with_artifacts
    plugin = AutofixPlugin(
        today=date(2026, 4, 17), apply=False,
        config={"fix_classes": {"claude_md_link": {"enabled": False}}},
    )
    result = plugin.scan(_ctx(repo))
    payload = json.loads(
        (repo / "integrity-out" / "2026-04-17" / "autofix.json").read_text()
    )
    assert "claude_md_link" not in payload["fix_classes_run"]
    assert any(
        i.rule == "autofix.skipped_disabled" and i.evidence.get("class") == "claude_md_link"
        for i in result.issues
    )
