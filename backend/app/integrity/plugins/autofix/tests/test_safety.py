"""Tests for safety preflight — 7 refusal modes."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.integrity.plugins.autofix.diff import Diff, IssueRef
from app.integrity.plugins.autofix.loader import SiblingArtifacts
from app.integrity.plugins.autofix.safety import (
    check_apply_preflight,
    check_diff_path,
    check_upstream,
)


def _ref() -> IssueRef:
    return IssueRef(plugin="x", rule="y", message="z", evidence={})


def _ok_artifacts() -> SiblingArtifacts:
    return SiblingArtifacts(
        doc_audit={"plugin": "doc_audit"},
        config_registry={"plugin": "config_registry"},
        graph_lint={"plugin": "graph_lint"},
        aggregate={"plugins": {}},
        failures={},
    )


def test_upstream_ok_when_all_present() -> None:
    verdict = check_upstream(_ok_artifacts())
    assert verdict.ok is True


def test_upstream_skip_when_artifact_missing() -> None:
    artifacts = SiblingArtifacts(
        doc_audit=None, config_registry={"x": 1},
        graph_lint={"y": 1}, aggregate={"z": 1},
        failures={"doc_audit": "missing"},
    )
    verdict = check_upstream(artifacts)
    assert verdict.ok is False
    assert verdict.rule == "autofix.skipped_upstream_missing"
    assert verdict.severity == "INFO"


def test_upstream_skip_when_artifact_parse_error() -> None:
    artifacts = SiblingArtifacts(
        doc_audit=None, config_registry={"x": 1},
        graph_lint={"y": 1}, aggregate={"z": 1},
        failures={"doc_audit": "parse_error: SyntaxError"},
    )
    verdict = check_upstream(artifacts)
    assert verdict.ok is False
    assert verdict.rule == "autofix.skipped_upstream_failure"
    assert verdict.severity == "INFO"


def _git(out: str = "", code: int = 0):
    from subprocess import CompletedProcess
    return CompletedProcess(args=[], returncode=code, stdout=out, stderr="")


def test_apply_ok_when_clean_tree_and_remote_and_gh(tmp_path: Path) -> None:
    with patch("subprocess.run") as run, patch("shutil.which", return_value="/usr/bin/gh"):
        run.side_effect = [
            _git(""),
            _git("git@github.com:o/r.git\n"),
        ]
        verdict = check_apply_preflight(tmp_path, gh_executable="gh")
    assert verdict.ok is True


def test_apply_refuses_dirty_tree(tmp_path: Path) -> None:
    with patch("subprocess.run") as run, patch("shutil.which", return_value="/usr/bin/gh"):
        run.side_effect = [
            _git(" M README.md\n"),
            _git("git@github.com:o/r.git\n"),
        ]
        verdict = check_apply_preflight(tmp_path, gh_executable="gh")
    assert verdict.ok is False
    assert verdict.rule == "apply.dirty_tree"
    assert verdict.severity == "ERROR"


def test_apply_refuses_when_gh_unavailable(tmp_path: Path) -> None:
    with patch("subprocess.run") as run, patch("shutil.which", return_value=None):
        run.side_effect = [_git(""), _git("git@github.com:o/r.git\n")]
        verdict = check_apply_preflight(tmp_path, gh_executable="gh")
    assert verdict.ok is False
    assert verdict.rule == "apply.gh_unavailable"


def test_apply_refuses_when_no_remote(tmp_path: Path) -> None:
    with patch("subprocess.run") as run, patch("shutil.which", return_value="/usr/bin/gh"):
        run.side_effect = [
            _git(""),
            _git("", code=128),
        ]
        verdict = check_apply_preflight(tmp_path, gh_executable="gh")
    assert verdict.ok is False
    assert verdict.rule == "apply.no_remote"


def test_diff_path_escape_refused(tmp_path: Path) -> None:
    d = Diff(
        path=Path("../../etc/passwd"),
        original_content="",
        new_content="x",
        rationale="r",
        source_issues=(_ref(),),
    )
    verdict = check_diff_path(d, repo_root=tmp_path)
    assert verdict.ok is False
    assert verdict.rule == "apply.path_escape"


def test_diff_path_inside_repo_ok(tmp_path: Path) -> None:
    d = Diff(
        path=Path("docs/foo.md"),
        original_content="",
        new_content="x",
        rationale="r",
        source_issues=(_ref(),),
    )
    verdict = check_diff_path(d, repo_root=tmp_path)
    assert verdict.ok is True
