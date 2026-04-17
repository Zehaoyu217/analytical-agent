from pathlib import Path

from backend.app.integrity.plugins.doc_audit.index import MarkdownIndex


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_builds_link_graph_and_indexes_anchors(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# Index\n\n- [Setup](docs/dev-setup.md)\n- [Test](docs/testing.md)\n")
    _write(tmp_path, "docs/dev-setup.md", "## Quick Start\n\nGo to [testing](testing.md#fast).\n")
    _write(tmp_path, "docs/testing.md", "## Fast\n\nSomething.\n")
    _write(tmp_path, "docs/orphan.md", "Not linked from anywhere.\n")

    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": [],
        "claude_ignore_file": ".claude-ignore",
    }
    idx = MarkdownIndex.build(tmp_path, cfg)

    assert "CLAUDE.md" in idx.docs
    assert "docs/dev-setup.md" in idx.docs
    assert "docs/testing.md" in idx.docs
    assert "docs/orphan.md" in idx.docs
    assert idx.link_graph["CLAUDE.md"] >= {"docs/dev-setup.md", "docs/testing.md"}
    assert idx.link_graph["docs/dev-setup.md"] >= {"docs/testing.md"}
    assert "fast" in idx.anchors_by_path["docs/testing.md"]


def test_excluded_paths_drop_files(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# X\n")
    _write(tmp_path, "docs/health/latest.md", "# generated\n")
    _write(tmp_path, "docs/dev-setup.md", "# real\n")
    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": ["docs/health/**"],
        "claude_ignore_file": ".claude-ignore",
    }
    idx = MarkdownIndex.build(tmp_path, cfg)
    assert "docs/dev-setup.md" in idx.docs
    assert "docs/health/latest.md" not in idx.docs
    assert "docs/health/latest.md" in idx.excluded


def test_ignored_paths_loaded_from_claude_ignore(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# X\n")
    _write(tmp_path, ".claude-ignore", "docs/draft/**\n")
    _write(tmp_path, "docs/draft/foo.md", "# draft\n")
    _write(tmp_path, "docs/published.md", "# published\n")
    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": [],
        "claude_ignore_file": ".claude-ignore",
    }
    idx = MarkdownIndex.build(tmp_path, cfg)
    assert "docs/draft/foo.md" in idx.docs   # still parsed
    assert "docs/draft/foo.md" in idx.ignored
    assert "docs/published.md" not in idx.ignored
