"""Tests for claude_md_link fixer."""
from __future__ import annotations

from pathlib import Path

from app.integrity.plugins.autofix.fixers.claude_md_link import propose
from app.integrity.plugins.autofix.loader import SiblingArtifacts


def _artifacts_with_unindexed(*paths: str) -> SiblingArtifacts:
    issues = [
        {"rule": "doc.unindexed", "evidence": {"path": p},
         "message": f"{p} not indexed", "severity": "WARN",
         "node_id": p, "location": p, "fix_class": None, "first_seen": ""}
        for p in paths
    ]
    return SiblingArtifacts(
        doc_audit={"plugin": "doc_audit", "issues": issues},
        config_registry={}, graph_lint={}, aggregate={}, failures={},
    )


def test_no_unindexed_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# T\n\n## Deeper Context\n\n- [Existing](docs/existing.md)\n")  # noqa: E501
    artifacts = SiblingArtifacts(
        doc_audit={"plugin": "doc_audit", "issues": []},
        config_registry={}, graph_lint={}, aggregate={}, failures={},
    )
    diffs = propose(artifacts, tmp_path, {})
    assert diffs == []


def test_appends_single_unindexed_doc(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "# T\n\n## Deeper Context\n\n- [Existing](docs/existing.md)\n"
    )
    target = tmp_path / "docs" / "foo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Foo Title\n\nbody\n")

    artifacts = _artifacts_with_unindexed("docs/foo.md")
    diffs = propose(artifacts, tmp_path, {"target_section": "## Deeper Context"})

    assert len(diffs) == 1
    assert diffs[0].path == Path("CLAUDE.md")
    assert "[Foo Title](docs/foo.md)" in diffs[0].new_content
    assert "Existing" in diffs[0].new_content


def test_bundles_multiple_unindexed_into_one_diff(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "# T\n\n## Deeper Context\n\n- [Existing](docs/existing.md)\n"
    )
    for p, title in [("docs/a.md", "A"), ("docs/b.md", "B")]:
        full = tmp_path / p
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(f"# {title}\n")

    artifacts = _artifacts_with_unindexed("docs/a.md", "docs/b.md")
    diffs = propose(artifacts, tmp_path, {"target_section": "## Deeper Context"})

    assert len(diffs) == 1
    assert "[A](docs/a.md)" in diffs[0].new_content
    assert "[B](docs/b.md)" in diffs[0].new_content


def test_skips_doc_already_in_claude_md(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "# T\n\n## Deeper Context\n\n- [Foo Title](docs/foo.md)\n"
    )
    full = tmp_path / "docs" / "foo.md"
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("# Foo Title\n")

    artifacts = _artifacts_with_unindexed("docs/foo.md")
    diffs = propose(artifacts, tmp_path, {"target_section": "## Deeper Context"})
    assert diffs == []


def test_uses_filename_titlecase_when_h1_missing(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# T\n\n## Deeper Context\n\n")
    full = tmp_path / "docs" / "my-thing.md"
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("no h1 here\n")

    artifacts = _artifacts_with_unindexed("docs/my-thing.md")
    diffs = propose(artifacts, tmp_path, {"target_section": "## Deeper Context"})
    assert "[My Thing](docs/my-thing.md)" in diffs[0].new_content
