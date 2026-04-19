import json
from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.doc_audit.rules.dead_code_ref import run
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _ctx_with_graph(repo: Path, nodes: list[dict]) -> ScanContext:
    g = repo / "graphify"
    g.mkdir(parents=True, exist_ok=True)
    (g / "graph.json").write_text(json.dumps({"nodes": nodes, "links": []}), encoding="utf-8")
    return ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))


_CFG = {
    "doc_roots": ["*.md", "docs/**/*.md", "knowledge/**/*.md"],
    "excluded_paths": [],
    "seed_docs": ["CLAUDE.md"],
    "claude_ignore_file": ".claude-ignore",
}


def test_missing_path_ref_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/dead.md", "See `backend/app/missing.py:42` for details.\n")
    nodes = [{"id": "foo.do_thing", "label": "do_thing", "source_file": "backend/app/foo.py"}]
    issues = run(_ctx_with_graph(tmp_path, nodes), _CFG, date(2026, 4, 17))
    matching = [i for i in issues if "dead.md" in i.location]
    assert len(matching) >= 1
    assert any(i.evidence["code_ref"].startswith("`backend/app/missing.py:42`") for i in matching)


def test_missing_qualified_symbol_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/sym.md", "Calls `Module.gone_func` somewhere.\n")
    nodes = [{"id": "module.live_func", "label": "live_func", "source_file": "backend/app/module.py"}]  # noqa: E501
    issues = run(_ctx_with_graph(tmp_path, nodes), _CFG, date(2026, 4, 17))
    matching = [i for i in issues if "sym.md" in i.location]
    assert len(matching) == 1
    assert "Module.gone_func" in matching[0].evidence["code_ref"]


def test_live_path_ref_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/live.md", "See `backend/app/foo.py:42`.\n")
    _write(tmp_path, "backend/app/foo.py", "# real file\n")
    nodes = [{"id": "foo.do_thing", "label": "do_thing", "source_file": "backend/app/foo.py"}]
    issues = run(_ctx_with_graph(tmp_path, nodes), _CFG, date(2026, 4, 17))
    matching = [i for i in issues if "live.md" in i.location]
    assert matching == []


def test_unqualified_symbol_not_flagged(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "docs/prose.md", "The variable `config` is widely used.\n")
    issues = run(_ctx_with_graph(tmp_path, []), _CFG, date(2026, 4, 17))
    matching = [i for i in issues if "prose.md" in i.location]
    assert matching == []


def test_adr_paths_excluded_from_dead_code_ref(tmp_path: Path):
    _write(tmp_path, "CLAUDE.md", "# x\n")
    _write(tmp_path, "knowledge/adr/001-foo.md", "References `backend/app/missing.py`.\n")
    issues = run(_ctx_with_graph(tmp_path, []), _CFG, date(2026, 4, 17))
    assert all("knowledge/adr/" not in i.location for i in issues)
