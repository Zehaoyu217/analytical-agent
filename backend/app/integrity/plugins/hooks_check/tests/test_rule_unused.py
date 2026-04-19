"""Tests for hooks.unused rule."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.integrity.plugins.hooks_check.coverage import (
    CoverageDoc,
    CoverageRule,
    CoverageWhen,
    RequiredHook,
)
from app.integrity.plugins.hooks_check.rules.unused import run as unused_run
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


def _hook(command: str, event: str = "PostToolUse",
          matcher: str = "Write|Edit") -> HookRecord:
    return HookRecord(event=event, matcher=matcher,
                      command=command, source_index=(0, 0, 0))


def test_unused_hook_emits_info(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "ruff"),), tolerated=()),
        "_hooks": [_hook("uv run ruff"), _hook("orphan_command_xyz")],
    }
    issues = unused_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "hooks.unused"
    assert issues[0].severity == "INFO"
    assert "orphan_command_xyz" in issues[0].message


def test_used_hook_emits_nothing(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "ruff"),), tolerated=()),
        "_hooks": [_hook("uv run ruff")],
    }
    issues = unused_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_tolerated_substring_suppresses(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(_rule("a", "ruff"),),
                                 tolerated=("sb inject",)),
        "_hooks": [
            _hook("uv run ruff"),
            _hook("sb inject --k 5", event="UserPromptSubmit", matcher=""),
        ],
    }
    issues = unused_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_partial_tolerated_substring_match_works(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(), tolerated=("prettier",)),
        "_hooks": [_hook("pnpm prettier --write")],
    }
    issues = unused_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_evidence_carries_full_command(tmp_path: Path) -> None:
    cfg = {
        "_coverage": CoverageDoc(rules=(), tolerated=()),
        "_hooks": [_hook("orphan command here")],
    }
    issues = unused_run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues[0].evidence["command"] == "orphan command here"
