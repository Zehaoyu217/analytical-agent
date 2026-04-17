"""Tests for config.removed rule."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.config_registry.manifest import empty_manifest
from backend.app.integrity.plugins.config_registry.rules.removed import (
    build_dep_index,
    run,
)
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _ctx(repo: Path) -> ScanContext:
    return ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))


def test_emits_info_for_orphan_removal(tiny_repo: Path) -> None:
    prior = empty_manifest()
    prior["scripts"] = [{"id": "scripts/totally-gone.sh"}]  # not in graph
    current = empty_manifest()
    cfg = {"_prior_manifest": prior, "_current_manifest": current,
           "_dep_graph": build_dep_index(GraphSnapshot.load(tiny_repo)),
           "removed_escalation": {"enabled": True}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].severity == "INFO"
    assert issues[0].node_id == "scripts/totally-gone.sh"


def test_escalates_to_warn_when_referenced(tiny_repo: Path) -> None:
    """If removed id appears in graph node id or source_file → WARN."""
    prior = empty_manifest()
    # legacy_removed.py is in the graph snapshot's source_file values
    prior["configs"] = [{"id": "backend/app/api/legacy_removed.py"}]
    current = empty_manifest()
    cfg = {"_prior_manifest": prior, "_current_manifest": current,
           "_dep_graph": build_dep_index(GraphSnapshot.load(tiny_repo)),
           "removed_escalation": {"enabled": True}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].severity == "WARN"
    assert "still referenced" in issues[0].message.lower()


def test_no_escalation_when_disabled(tiny_repo: Path) -> None:
    prior = empty_manifest()
    prior["configs"] = [{"id": "backend/app/api/legacy_removed.py"}]
    current = empty_manifest()
    cfg = {"_prior_manifest": prior, "_current_manifest": current,
           "_dep_graph": build_dep_index(GraphSnapshot.load(tiny_repo)),
           "removed_escalation": {"enabled": False}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].severity == "INFO"


def test_no_diff_no_issues(tiny_repo: Path) -> None:
    m = empty_manifest()
    cfg = {"_prior_manifest": m, "_current_manifest": m,
           "_dep_graph": build_dep_index(GraphSnapshot.load(tiny_repo)),
           "removed_escalation": {"enabled": True}}
    assert run(_ctx(tiny_repo), cfg, date(2026, 4, 17)) == []
