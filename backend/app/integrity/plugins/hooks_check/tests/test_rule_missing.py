"""Tests for hooks.missing rule."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.integrity.plugins.hooks_check.coverage import (
    CoverageDoc,
    CoverageRule,
    CoverageWhen,
    RequiredHook,
)
from app.integrity.plugins.hooks_check.rules.missing import run as missing_run
from app.integrity.plugins.hooks_check.settings_parser import HookRecord


def _ctx(tmp_path: Path):
    from app.integrity.protocol import ScanContext
    from app.integrity.schema import GraphSnapshot
    return ScanContext(repo_root=tmp_path, graph=GraphSnapshot(nodes=[], links=[]))


def _rule(rid: str, substr: str) -> CoverageRule:
    return CoverageRule(
        id=rid, description="d",
        when=CoverageWhen(paths=("*.py",)),
        requires_hook=RequiredHook(
            event="PostToolUse", matcher="Write|Edit", command_substring=substr,
        ),
    )


def _hook(command: str, matcher: str = "Write|Edit") -> HookRecord:
    return HookRecord(
        event="PostToolUse", matcher=matcher,
        command=command, source_index=(0, 0, 0),
    )


def test_missing_emits_warn(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "needs_this"),), tolerated=()),
        "_hooks": [_hook("echo nope")],
    }
    issues = missing_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "hooks.missing"
    assert issues[0].severity == "WARN"
    assert issues[0].node_id == "a"


def test_satisfied_emits_nothing(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "ruff"),), tolerated=()),
        "_hooks": [_hook("uv run ruff check")],
    }
    issues = missing_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_evidence_includes_required_fields(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "X"),), tolerated=()),
        "_hooks": [],
    }
    issues = missing_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    ev = issues[0].evidence
    assert ev["required_event"] == "PostToolUse"
    assert ev["required_matcher"] == "Write|Edit"
    assert ev["required_substring"] == "X"
    assert ev["rule_paths"] == ["*.py"]
