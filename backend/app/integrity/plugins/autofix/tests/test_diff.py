"""Tests for the Diff dataclass — the core unit of autofix proposals."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.integrity.plugins.autofix.diff import Diff, IssueRef


def _ref() -> IssueRef:
    return IssueRef(
        plugin="doc_audit",
        rule="doc.unindexed",
        message="docs/foo.md not indexed in CLAUDE.md",
        evidence={"path": "docs/foo.md"},
    )


def test_diff_is_frozen() -> None:
    d = Diff(
        path=Path("CLAUDE.md"),
        original_content="a\n",
        new_content="b\n",
        rationale="x",
        source_issues=(_ref(),),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.path = Path("other.md")  # type: ignore[misc]


def test_is_noop_true_when_contents_equal() -> None:
    d = Diff(
        path=Path("CLAUDE.md"),
        original_content="same\n",
        new_content="same\n",
        rationale="no-op",
        source_issues=(_ref(),),
    )
    assert d.is_noop() is True


def test_is_noop_false_when_contents_differ() -> None:
    d = Diff(
        path=Path("CLAUDE.md"),
        original_content="old\n",
        new_content="new\n",
        rationale="rewrite",
        source_issues=(_ref(),),
    )
    assert d.is_noop() is False


def test_stale_against_true_when_disk_changed(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("disk-content\n")
    d = Diff(
        path=Path("CLAUDE.md"),
        original_content="snapshot-content\n",
        new_content="new-content\n",
        rationale="stale",
        source_issues=(_ref(),),
    )
    assert d.stale_against(tmp_path) is True


def test_stale_against_false_when_disk_matches_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("snapshot-content\n")
    d = Diff(
        path=Path("CLAUDE.md"),
        original_content="snapshot-content\n",
        new_content="new-content\n",
        rationale="fresh",
        source_issues=(_ref(),),
    )
    assert d.stale_against(tmp_path) is False


def test_stale_against_treats_missing_file_as_stale_unless_creating(tmp_path: Path) -> None:
    d_create = Diff(
        path=Path("new.md"),
        original_content="",
        new_content="hello\n",
        rationale="create",
        source_issues=(_ref(),),
    )
    assert d_create.stale_against(tmp_path) is False

    d_modify = Diff(
        path=Path("missing.md"),
        original_content="expected\n",
        new_content="new\n",
        rationale="modify",
        source_issues=(_ref(),),
    )
    assert d_modify.stale_against(tmp_path) is True


def test_diff_path_must_be_relative() -> None:
    with pytest.raises(ValueError, match="must be relative"):
        Diff(
            path=Path("/absolute/path"),
            original_content="",
            new_content="x\n",
            rationale="abs",
            source_issues=(_ref(),),
        )
