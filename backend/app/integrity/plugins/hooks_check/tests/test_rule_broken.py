"""Tests for hooks.broken rule (real subprocess)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.integrity.plugins.hooks_check.coverage import (
    CoverageDoc,
    CoverageRule,
    CoverageWhen,
    RequiredHook,
)
from app.integrity.plugins.hooks_check.rules.broken import run as broken_run
from app.integrity.plugins.hooks_check.settings_parser import HookRecord

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _ctx(tmp_path: Path):
    from app.integrity.protocol import ScanContext
    from app.integrity.schema import GraphSnapshot
    return ScanContext(repo_root=tmp_path, graph=GraphSnapshot(nodes=[], links=[]))


def _rule(rid: str, substr: str) -> CoverageRule:
    return CoverageRule(
        id=rid, description="d",
        when=CoverageWhen(paths=("*.py",)),
        requires_hook=RequiredHook(
            event="PostToolUse", matcher="Write", command_substring=substr,
        ),
    )


def _hook(command: str) -> HookRecord:
    return HookRecord(event="PostToolUse", matcher="Write",
                      command=command, source_index=(0, 0, 0))


def test_broken_hook_emits_warn(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "false"),), tolerated=()),
        "_hooks": [_hook("false")],
        "_dry_run_timeout": 5,
        "_fixtures_dir": FIXTURES,
    }
    issues = broken_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "hooks.broken"
    assert issues[0].severity == "WARN"
    assert issues[0].evidence["exit_code"] == 1


def test_green_hook_emits_nothing(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "echo"),), tolerated=()),
        "_hooks": [_hook("echo green")],
        "_dry_run_timeout": 5,
        "_fixtures_dir": FIXTURES,
    }
    issues = broken_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_unmatched_rule_skipped(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "no_hook_has_this_substr"),), tolerated=()),
        "_hooks": [_hook("echo other")],
        "_dry_run_timeout": 5,
        "_fixtures_dir": FIXTURES,
    }
    issues = broken_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_timeout_emits_warn_with_timed_out_message(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "sleep"),), tolerated=()),
        "_hooks": [_hook("sleep 30")],
        "_dry_run_timeout": 1,
        "_fixtures_dir": FIXTURES,
    }
    issues = broken_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert "timed out" in issues[0].message
