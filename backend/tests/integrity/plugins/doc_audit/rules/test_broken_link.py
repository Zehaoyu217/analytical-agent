from datetime import date
from pathlib import Path
from unittest.mock import patch

from backend.app.integrity.plugins.doc_audit.rules.broken_link import run
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


_BASE_CFG = {
    "doc_roots": ["*.md", "docs/**/*.md", "knowledge/**/*.md"],
    "excluded_paths": [],
    "seed_docs": ["CLAUDE.md"],
    "claude_ignore_file": ".claude-ignore",
    "rename_lookback": "30.days.ago",
}


def test_broken_file_link_emits_issue(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/broken.md", "See [gone](gone.md) for details.\n")

    with patch(
        "backend.app.integrity.plugins.doc_audit.rules.broken_link.recent_renames",
        return_value={},
    ):
        issues = run(_ctx(tmp_path), _BASE_CFG, date(2026, 4, 17))
    matching = [i for i in issues if i.location.startswith("docs/broken.md")]
    assert len(matching) == 1
    issue = matching[0]
    assert issue.rule == "doc.broken_link"
    assert issue.severity == "WARN"
    assert issue.fix_class is None
    assert issue.evidence["target"] == "docs/gone.md"


def test_broken_anchor_emits_issue(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/target.md", "## Real Section\n")
    _write(tmp_path, "docs/anchor.md", "Link [there](target.md#nonexistent).\n")

    with patch(
        "backend.app.integrity.plugins.doc_audit.rules.broken_link.recent_renames",
        return_value={},
    ):
        issues = run(_ctx(tmp_path), _BASE_CFG, date(2026, 4, 17))
    matching = [i for i in issues if "anchor.md" in i.location]
    assert len(matching) == 1
    assert matching[0].evidence["anchor"] == "nonexistent"


def test_recent_rename_downgrades_to_doc_link_renamed(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/source.md", "See [old](old-name.md).\n")

    with patch(
        "backend.app.integrity.plugins.doc_audit.rules.broken_link.recent_renames",
        return_value={"docs/old-name.md": "docs/new-name.md"},
    ):
        issues = run(_ctx(tmp_path), _BASE_CFG, date(2026, 4, 17))
    matching = [i for i in issues if "source.md" in i.location]
    assert len(matching) == 1
    issue = matching[0]
    assert issue.fix_class == "doc_link_renamed"
    assert issue.evidence["rename_to"] == "docs/new-name.md"


def test_absolute_url_not_checked(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "[ext](https://example.com/whatever).\n")

    with patch(
        "backend.app.integrity.plugins.doc_audit.rules.broken_link.recent_renames",
        return_value={},
    ):
        issues = run(_ctx(tmp_path), _BASE_CFG, date(2026, 4, 17))
    assert issues == []


def test_valid_link_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/a.md", "See [b](b.md#sec).\n")
    _write(tmp_path, "docs/b.md", "## Sec\n")

    with patch(
        "backend.app.integrity.plugins.doc_audit.rules.broken_link.recent_renames",
        return_value={},
    ):
        issues = run(_ctx(tmp_path), _BASE_CFG, date(2026, 4, 17))
    assert issues == []


def test_in_page_anchor_validated(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/inpage.md", "## Top\n\nGo [here](#nope) and [there](#top).\n")

    with patch(
        "backend.app.integrity.plugins.doc_audit.rules.broken_link.recent_renames",
        return_value={},
    ):
        issues = run(_ctx(tmp_path), _BASE_CFG, date(2026, 4, 17))
    matching = [i for i in issues if "inpage.md" in i.location]
    assert len(matching) == 1
    assert matching[0].evidence["anchor"] == "nope"
