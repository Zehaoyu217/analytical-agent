"""Tests for the autofix sync subcommand — updates autofix_state.yaml from
merged PRs."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import yaml

from backend.app.integrity.plugins.autofix.sync import sync_state


def _ok(stdout: str = "") -> CompletedProcess:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_sync_records_clean_merge(tmp_path: Path) -> None:
    state_path = tmp_path / "config" / "autofix_state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump({
        "window_days": 30, "classes": {}
    }))

    pr_list = (
        '[{"number":42,"headRefName":"integrity/autofix/claude_md_link/2026-04-10",'
        '"mergedAt":"2026-04-12T00:00:00Z","state":"MERGED"}]'
    )
    diff_log = "+- [Foo](docs/foo.md)\n"

    def fake_run(args, **kwargs):
        if args[0] == "gh" and "list" in args:
            return _ok(pr_list)
        if args[0] == "git" and "log" in args:
            return _ok(diff_log)
        if args[0] == "git" and "diff" in args:
            return _ok(diff_log)  # identical → clean
        return _ok("")

    with patch("subprocess.run", side_effect=fake_run):
        sync_state(repo_root=tmp_path, state_path=state_path,
                   today=date(2026, 4, 13))

    state = yaml.safe_load(state_path.read_text())
    assert state["classes"]["claude_md_link"]["merged_clean"] == 1
    assert state["classes"]["claude_md_link"]["human_edited"] == 0


def test_sync_records_human_edit_when_diff_differs(tmp_path: Path) -> None:
    state_path = tmp_path / "config" / "autofix_state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump({"window_days": 30, "classes": {}}))

    pr_list = (
        '[{"number":42,"headRefName":"integrity/autofix/claude_md_link/2026-04-10",'
        '"mergedAt":"2026-04-12T00:00:00Z","state":"MERGED"}]'
    )

    def fake_run(args, **kwargs):
        if args[0] == "gh" and "list" in args:
            return _ok(pr_list)
        if args[0] == "git" and "log" in args:
            return _ok("+- [Foo](docs/foo.md)\n")  # original
        if args[0] == "git" and "diff" in args:
            return _ok("+- [Foo](docs/foo.md)\n+- [Manual](docs/m.md)\n")  # edited
        return _ok("")

    with patch("subprocess.run", side_effect=fake_run):
        sync_state(repo_root=tmp_path, state_path=state_path,
                   today=date(2026, 4, 13))

    state = yaml.safe_load(state_path.read_text())
    assert state["classes"]["claude_md_link"]["human_edited"] == 1
    assert state["classes"]["claude_md_link"]["merged_clean"] == 0
