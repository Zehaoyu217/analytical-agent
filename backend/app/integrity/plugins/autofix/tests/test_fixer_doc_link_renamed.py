"""Tests for doc_link_renamed fixer."""
from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from app.integrity.plugins.autofix.fixers.doc_link_renamed import propose
from app.integrity.plugins.autofix.loader import SiblingArtifacts


def _artifacts(broken: list[tuple[str, str]]) -> SiblingArtifacts:
    issues = [
        {"rule": "doc.broken_link",
         "evidence": {"source": s, "link_target": t},
         "message": f"{s} -> {t}", "severity": "WARN",
         "node_id": f"{s}->{t}", "location": s,
         "fix_class": None, "first_seen": ""}
        for s, t in broken
    ]
    return SiblingArtifacts(
        doc_audit={"plugin": "doc_audit", "issues": issues},
        config_registry={}, graph_lint={}, aggregate={}, failures={},
    )


def _git_log(stdout: str, code: int = 0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=code, stdout=stdout, stderr="")


def test_no_broken_links_returns_empty(tmp_path: Path) -> None:
    artifacts = SiblingArtifacts(
        doc_audit={"plugin": "doc_audit", "issues": []},
        config_registry={}, graph_lint={}, aggregate={}, failures={},
    )
    assert propose(artifacts, tmp_path, {}) == []


def test_rewrites_unique_rename(tmp_path: Path) -> None:
    src = tmp_path / "docs" / "a.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("see [link](docs/old/path.md) for details\n")

    artifacts = _artifacts([("docs/a.md", "docs/old/path.md")])
    log_out = "abc1234\n--- a/docs/old/path.md\n+++ b/docs/new/path.md\n"

    with patch("subprocess.run") as run:
        run.return_value = _git_log(log_out)
        diffs = propose(artifacts, tmp_path, {})

    assert len(diffs) == 1
    assert diffs[0].path == Path("docs/a.md")
    assert "docs/new/path.md" in diffs[0].new_content
    assert "docs/old/path.md" not in diffs[0].new_content


def test_skips_ambiguous_rename(tmp_path: Path) -> None:
    src = tmp_path / "docs" / "a.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("see [link](docs/old/path.md)\n")

    artifacts = _artifacts([("docs/a.md", "docs/old/path.md")])
    log_out = (
        "abc\n--- a/docs/old/path.md\n+++ b/docs/new1/path.md\n"
        "def\n--- a/docs/old/path.md\n+++ b/docs/new2/path.md\n"
    )
    with patch("subprocess.run") as run:
        run.return_value = _git_log(log_out)
        diffs = propose(artifacts, tmp_path, {})

    assert diffs == []


def test_skips_when_no_rename_history(tmp_path: Path) -> None:
    src = tmp_path / "docs" / "a.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("see [link](docs/old/path.md)\n")

    artifacts = _artifacts([("docs/a.md", "docs/old/path.md")])
    with patch("subprocess.run") as run:
        run.return_value = _git_log("")
        diffs = propose(artifacts, tmp_path, {})

    assert diffs == []


def test_groups_multiple_links_per_source_into_one_diff(tmp_path: Path) -> None:
    src = tmp_path / "docs" / "a.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("[x](docs/x.md) and [y](docs/y.md)\n")

    artifacts = _artifacts([
        ("docs/a.md", "docs/x.md"),
        ("docs/a.md", "docs/y.md"),
    ])

    def fake_log(*args, **kwargs):
        argv = args[0]
        target = argv[-1]
        if target == "docs/x.md":
            return _git_log("abc\n--- a/docs/x.md\n+++ b/docs/X.md\n")
        if target == "docs/y.md":
            return _git_log("def\n--- a/docs/y.md\n+++ b/docs/Y.md\n")
        return _git_log("")

    with patch("subprocess.run", side_effect=fake_log):
        diffs = propose(artifacts, tmp_path, {})

    assert len(diffs) == 1
    assert "docs/X.md" in diffs[0].new_content
    assert "docs/Y.md" in diffs[0].new_content
