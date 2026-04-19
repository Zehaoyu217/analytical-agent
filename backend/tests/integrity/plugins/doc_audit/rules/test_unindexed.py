from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.doc_audit.rules.unindexed import run
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _ctx(repo: Path) -> ScanContext:
    g = repo / "graphify"
    g.mkdir(parents=True, exist_ok=True)
    (g / "graph.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")
    return ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))


def test_orphan_doc_emits_issue(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# index\n\n- [Setup](docs/dev-setup.md)\n")
    _write(tmp_path, "docs/dev-setup.md", "# setup\n")
    _write(tmp_path, "docs/orphan.md", "no inbound links\n")

    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": [],
        "seed_docs": ["CLAUDE.md"],
        "claude_ignore_file": ".claude-ignore",
    }
    issues = run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule == "doc.unindexed"
    assert issue.severity == "WARN"
    assert issue.node_id == "docs/orphan.md"
    assert issue.fix_class == "claude_md_link"
    assert "CLAUDE.md" in issue.evidence["seed_docs"]


def test_reachable_doc_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "- [Setup](docs/dev-setup.md)\n")
    _write(tmp_path, "docs/dev-setup.md", "- [Test](testing.md)\n")  # transitively reaches testing.md  # noqa: E501
    _write(tmp_path, "docs/testing.md", "# tests\n")

    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": [],
        "seed_docs": ["CLAUDE.md"],
        "claude_ignore_file": ".claude-ignore",
    }
    issues = run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert issues == []


def test_ignored_doc_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, ".claude-ignore", "docs/scratch/**\n")
    _write(tmp_path, "docs/scratch/notes.md", "# scratch\n")

    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": [],
        "seed_docs": ["CLAUDE.md"],
        "claude_ignore_file": ".claude-ignore",
    }
    issues = run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert all(i.node_id != "docs/scratch/notes.md" for i in issues)


def test_excluded_doc_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/health/latest.md", "# generated\n")

    cfg = {
        "doc_roots": ["*.md", "docs/**/*.md"],
        "excluded_paths": ["docs/health/**"],
        "seed_docs": ["CLAUDE.md"],
        "claude_ignore_file": ".claude-ignore",
    }
    issues = run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    assert all(i.node_id != "docs/health/latest.md" for i in issues)


def test_seed_docs_themselves_never_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "README.md", "# x\n")

    cfg = {
        "doc_roots": ["*.md"],
        "excluded_paths": [],
        "seed_docs": ["CLAUDE.md"],
        "claude_ignore_file": ".claude-ignore",
    }
    issues = run(_ctx(tmp_path), cfg, date(2026, 4, 17))
    # CLAUDE.md is a seed; README.md is a top-level doc not reached → flagged
    flagged = {i.node_id for i in issues}
    assert "CLAUDE.md" not in flagged
    assert "README.md" in flagged
