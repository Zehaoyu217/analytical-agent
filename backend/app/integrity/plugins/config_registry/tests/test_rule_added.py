"""Tests for config.added rule."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.config_registry.manifest import empty_manifest
from backend.app.integrity.plugins.config_registry.rules.added import run
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _ctx(repo: Path) -> ScanContext:
    return ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))


def test_emits_info_for_new_script(tiny_repo: Path) -> None:
    prior = empty_manifest()
    current = empty_manifest()
    current["scripts"] = [{"id": "scripts/new.sh", "path": "scripts/new.sh",
                           "interpreter": "bash", "sha": "x"}]
    cfg = {"_prior_manifest": prior, "_current_manifest": current}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "config.added"
    assert issues[0].severity == "INFO"
    assert issues[0].node_id == "scripts/new.sh"


def test_no_diff_no_issues(tiny_repo: Path) -> None:
    m = empty_manifest()
    cfg = {"_prior_manifest": m, "_current_manifest": m}
    assert run(_ctx(tiny_repo), cfg, date(2026, 4, 17)) == []


def test_added_across_all_keys(tiny_repo: Path) -> None:
    prior = empty_manifest()
    current = empty_manifest()
    current["skills"] = [{"id": "alpha"}]
    current["scripts"] = [{"id": "scripts/a.sh"}]
    current["routes"] = [{"id": "route::GET::/x"}]
    current["configs"] = [{"id": "Makefile"}]
    current["functions"] = [{"id": "backend.app.api.x.y"}]
    cfg = {"_prior_manifest": prior, "_current_manifest": current}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert len(issues) == 5
    assert {i.rule for i in issues} == {"config.added"}
