"""Tests for the PR dispatcher — verifies exact git/gh argv sequences (create flow)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from app.integrity.plugins.autofix.diff import Diff, IssueRef
from app.integrity.plugins.autofix.pr_dispatcher import (
    DispatcherConfig,
    PRResult,
    dispatch_class,
)


def _ref() -> IssueRef:
    return IssueRef(plugin="doc_audit", rule="doc.unindexed",
                    message="m", evidence={"path": "docs/foo.md"})


def _diff(tmp_path: Path) -> Diff:
    target = tmp_path / "CLAUDE.md"
    target.write_text("orig\n")
    return Diff(
        path=Path("CLAUDE.md"),
        original_content="orig\n",
        new_content="orig\n+- new entry\n",
        rationale="add entry",
        source_issues=(_ref(),),
    )


def _cfg(tmp_path: Path, *, dry_run: bool = False) -> DispatcherConfig:
    return DispatcherConfig(
        repo_root=tmp_path,
        branch_prefix="integrity/autofix",
        commit_author="Integrity Autofix <integrity@local>",
        gh_executable="gh",
        subprocess_timeout_seconds=60,
        today=date(2026, 4, 17),
        dry_run=dry_run,
    )


def _ok(out: str = "") -> CompletedProcess:
    return CompletedProcess(args=[], returncode=0, stdout=out, stderr="")


def test_dispatch_creates_pr_when_none_exists(tmp_path: Path) -> None:
    diff = _diff(tmp_path)
    cfg = _cfg(tmp_path)

    with patch("subprocess.run") as run:
        run.side_effect = [
            _ok(""),
            _ok(""),
            _ok(""),
            _ok(""),
            _ok(""),
            _ok(""),
            _ok("[]"),
            _ok('{"number":42,"url":"https://x/pr/42"}'),
        ]
        result = dispatch_class("claude_md_link", [diff], cfg)

    assert isinstance(result, PRResult)
    assert result.action == "created"
    assert result.pr_number == 42
    assert result.pr_url == "https://x/pr/42"
    assert result.diff_count == 1
    assert result.branch == "integrity/autofix/claude_md_link/2026-04-17"

    calls = [c.args[0] for c in run.call_args_list]
    assert calls[0][0:4] == ["git", "-C", str(tmp_path), "ls-remote"]
    assert calls[1][0:5] == ["git", "-C", str(tmp_path), "fetch", "origin"]
    assert calls[2][0:5] == ["git", "-C", str(tmp_path), "checkout", "-B"]
    assert "integrity/autofix/claude_md_link/2026-04-17" in calls[2]
    assert calls[3][0:4] == ["git", "-C", str(tmp_path), "add"]
    assert "CLAUDE.md" in calls[3]
    assert calls[4][0:3] == ["git", "-C", str(tmp_path)] and "commit" in calls[4]
    assert calls[5][0:4] == ["git", "-C", str(tmp_path), "push"]
    assert calls[6][0] == "gh" and "list" in calls[6]
    assert calls[7][0] == "gh" and "create" in calls[7]


def test_dispatch_writes_new_content_to_disk(tmp_path: Path) -> None:
    diff = _diff(tmp_path)
    cfg = _cfg(tmp_path)
    with patch("subprocess.run") as run:
        run.side_effect = [_ok("")] * 6 + [_ok("[]"), _ok('{"number":1,"url":"u"}')]
        dispatch_class("claude_md_link", [diff], cfg)
    assert (tmp_path / "CLAUDE.md").read_text() == "orig\n+- new entry\n"


def test_dispatch_skips_when_diffs_empty(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    with patch("subprocess.run") as run:
        result = dispatch_class("claude_md_link", [], cfg)
    assert result.action == "skipped"
    assert result.diff_count == 0
    assert run.call_count == 0


def test_dispatch_aborts_on_stale_diff(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    target = tmp_path / "CLAUDE.md"
    target.write_text("disk-changed\n")
    stale = Diff(
        path=Path("CLAUDE.md"),
        original_content="snapshot\n",
        new_content="new\n",
        rationale="r",
        source_issues=(_ref(),),
    )
    with patch("subprocess.run") as run:
        result = dispatch_class("claude_md_link", [stale], cfg)
    assert result.action == "errored"
    assert result.error_rule == "apply.stale_diff"
    assert run.call_count == 0


def test_dispatch_aborts_on_path_escape(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    bad = Diff(
        path=Path("../escape.md"),
        original_content="",
        new_content="x",
        rationale="r",
        source_issues=(_ref(),),
    )
    with patch("subprocess.run") as run:
        result = dispatch_class("claude_md_link", [bad], cfg)
    assert result.action == "errored"
    assert result.error_rule == "apply.path_escape"
    assert run.call_count == 0


def test_dispatch_dry_run_skips_subprocess(tmp_path: Path) -> None:
    diff = _diff(tmp_path)
    cfg = _cfg(tmp_path, dry_run=True)
    with patch("subprocess.run") as run:
        result = dispatch_class("claude_md_link", [diff], cfg)
    assert result.action == "dry_run"
    assert result.diff_count == 1
    assert run.call_count == 0
    assert (tmp_path / "CLAUDE.md").read_text() == "orig\n"
