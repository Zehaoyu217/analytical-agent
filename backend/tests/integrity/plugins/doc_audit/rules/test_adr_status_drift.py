import json
from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.doc_audit.rules.adr_status_drift import (
    is_accepted,
    run,
)
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _ctx(repo: Path, nodes: list[dict] | None = None) -> ScanContext:
    g = repo / "graphify"
    g.mkdir(parents=True, exist_ok=True)
    (g / "graph.json").write_text(
        json.dumps({"nodes": nodes or [], "links": []}), encoding="utf-8"
    )
    return ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))


_CFG = {
    "doc_roots": ["*.md", "knowledge/**/*.md"],
    "excluded_paths": [],
    "seed_docs": ["CLAUDE.md"],
    "claude_ignore_file": ".claude-ignore",
}


def test_is_accepted_recognizes_bold_line():
    text = "# ADR\n\n**Status:** Accepted\n\nBody.\n"
    assert is_accepted({}, text) is True


def test_is_accepted_recognizes_yaml_frontmatter():
    text = "Body.\n"
    assert is_accepted({"status": "accepted"}, text) is True
    assert is_accepted({"status": "Accepted"}, text) is True


def test_is_accepted_rejects_other_statuses():
    text = "**Status:** Proposed\n"
    assert is_accepted({}, text) is False
    assert is_accepted({"status": "deprecated"}, text) is False


def test_accepted_adr_with_dead_ref_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(
        tmp_path,
        "knowledge/adr/002-drift.md",
        "# ADR 002\n\n**Status:** Accepted\n\nReferences `backend/app/gone.py:10`.\n",
    )
    issues = run(_ctx(tmp_path), _CFG, date(2026, 4, 17))
    matching = [i for i in issues if "002-drift.md" in i.location]
    assert len(matching) == 1
    assert matching[0].rule == "doc.adr_status_drift"
    assert matching[0].severity == "WARN"


def test_accepted_adr_with_live_ref_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(
        tmp_path,
        "knowledge/adr/001-real.md",
        "# ADR 001\n\n**Status:** Accepted\n\nUses `backend/app/foo.py`.\n",
    )
    _write(tmp_path, "backend/app/foo.py", "# real\n")
    issues = run(
        _ctx(tmp_path, [{"id": "x", "label": "x", "source_file": "backend/app/foo.py"}]),
        _CFG,
        date(2026, 4, 17),
    )
    assert all("001-real.md" not in i.location for i in issues)


def test_proposed_adr_skipped(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(
        tmp_path,
        "knowledge/adr/003-prop.md",
        "# ADR 003\n\n**Status:** Proposed\n\nReferences `backend/app/gone.py`.\n",
    )
    issues = run(_ctx(tmp_path), _CFG, date(2026, 4, 17))
    assert all("003-prop.md" not in i.location for i in issues)


def test_template_excluded(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(
        tmp_path,
        "knowledge/adr/template.md",
        "# Template\n\n**Status:** Accepted\n\n`backend/app/missing.py`\n",
    )
    issues = run(_ctx(tmp_path), _CFG, date(2026, 4, 17))
    assert all("template.md" not in i.location for i in issues)


def test_yaml_frontmatter_accepted_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(
        tmp_path,
        "knowledge/adr/004-yaml.md",
        "---\nstatus: accepted\n---\n\n# ADR 004\n\nUses `backend/app/gone.py`.\n",
    )
    issues = run(_ctx(tmp_path), _CFG, date(2026, 4, 17))
    matching = [i for i in issues if "004-yaml.md" in i.location]
    assert len(matching) == 1
