"""Tests for the PR dispatcher — update flow + lease behavior."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from app.integrity.plugins.autofix.diff import Diff, IssueRef
from app.integrity.plugins.autofix.pr_dispatcher import (
    DispatcherConfig,
    dispatch_class,
)


def _ref() -> IssueRef:
    return IssueRef(plugin="x", rule="y", message="m", evidence={})


def _diff(tmp_path: Path) -> Diff:
    target = tmp_path / "CLAUDE.md"
    target.write_text("orig\n")
    return Diff(
        path=Path("CLAUDE.md"),
        original_content="orig\n",
        new_content="updated\n",
        rationale="r",
        source_issues=(_ref(),),
    )


def _cfg(tmp_path: Path) -> DispatcherConfig:
    return DispatcherConfig(
        repo_root=tmp_path,
        branch_prefix="integrity/autofix",
        commit_author="Integrity Autofix <integrity@local>",
        gh_executable="gh",
        subprocess_timeout_seconds=60,
        today=date(2026, 4, 17),
        dry_run=False,
    )


def _ok(out: str = "") -> CompletedProcess:
    return CompletedProcess(args=[], returncode=0, stdout=out, stderr="")


def test_dispatch_updates_existing_pr(tmp_path: Path) -> None:
    diff = _diff(tmp_path)
    cfg = _cfg(tmp_path)

    existing_pr = '[{"number":99,"url":"https://x/pr/99"}]'
    with patch("subprocess.run") as run:
        run.side_effect = [
            _ok("abc123\trefs/heads/integrity/autofix/claude_md_link/2026-04-17"),
            _ok(""),
            _ok(""),
            _ok(""),
            _ok(""),
            _ok(""),
            _ok(existing_pr),
            _ok(""),
        ]
        result = dispatch_class("claude_md_link", [diff], cfg)

    assert result.action == "updated"
    assert result.pr_number == 99
    assert result.pr_url == "https://x/pr/99"

    push_call = run.call_args_list[5].args[0]
    assert any("--force-with-lease=integrity/autofix/claude_md_link/2026-04-17:abc123" in a
               for a in push_call)


def test_dispatch_uses_unconditional_lease_when_branch_new(tmp_path: Path) -> None:
    diff = _diff(tmp_path)
    cfg = _cfg(tmp_path)
    with patch("subprocess.run") as run:
        run.side_effect = [
            _ok(""),
            _ok(""), _ok(""), _ok(""), _ok(""), _ok(""),
            _ok("[]"),
            _ok('{"number":1,"url":"u"}'),
        ]
        dispatch_class("claude_md_link", [diff], cfg)

    push_call = run.call_args_list[5].args[0]
    assert "--force-with-lease" in push_call
    assert not any(a.startswith("--force-with-lease=") for a in push_call)
