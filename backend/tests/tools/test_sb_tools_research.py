from __future__ import annotations

import importlib
from pathlib import Path

from second_brain.frontmatter import load_document


def _point_at_home(monkeypatch, home: Path, enabled: bool) -> None:
    if enabled:
        (home / ".sb").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    from app import config

    importlib.reload(config)


def test_sb_ingest_auto_compiles_center_and_reindexes(monkeypatch, tmp_path):
    home = tmp_path / "sb"
    _point_at_home(monkeypatch, home, enabled=True)
    note = tmp_path / "attention.md"
    note.write_text(
        "# Attention\n\nAttention is useful for sequence transduction.\n",
        encoding="utf-8",
    )

    from app.tools import sb_tools

    importlib.reload(sb_tools)
    res = sb_tools.sb_ingest({"path": str(note)})
    assert res["ok"] is True, res
    assert (home / ".sb" / "kb.sqlite").exists()
    paper_files = list((home / "papers").glob("*.md"))
    assert len(paper_files) == 1


def test_sb_promote_claim_refreshes_paper_links(monkeypatch, tmp_path):
    home = tmp_path / "sb"
    _point_at_home(monkeypatch, home, enabled=True)
    note = tmp_path / "attention.md"
    note.write_text(
        "# Attention\n\nAttention is useful for sequence transduction.\n",
        encoding="utf-8",
    )

    from app.tools import sb_tools

    importlib.reload(sb_tools)
    ingest = sb_tools.sb_ingest({"path": str(note)})
    assert ingest["ok"] is True

    promote = sb_tools.sb_promote_claim(
        {
            "statement": "Attention improves sequence transduction.",
            "kind": "empirical",
            "confidence": "high",
            "supports": [ingest["source_id"]],
            "abstract": "A promoted claim for the ingested note.",
        }
    )
    assert promote["ok"] is True, promote
    paper = next((home / "papers").glob("*.md"))
    _meta, body = load_document(paper)
    assert promote["claim_id"] in body


def test_sb_search_returns_brokered_titles(monkeypatch, tmp_path):
    home = tmp_path / "sb"
    _point_at_home(monkeypatch, home, enabled=True)
    note = tmp_path / "attention.md"
    note.write_text(
        "# Attention\n\nAttention is useful for sequence transduction.\n",
        encoding="utf-8",
    )

    from app.tools import sb_tools

    importlib.reload(sb_tools)
    ingest = sb_tools.sb_ingest({"path": str(note)})
    assert ingest["ok"] is True
    res = sb_tools.sb_search({"query": "attention", "k": 3, "scope": "both"})
    assert res["ok"] is True
    assert res["hits"]
    assert "title" in res["hits"][0]
    evidence = res["hits"][0]["evidence"]
    assert evidence
    assert "source_id" in evidence[0]
    assert "page_start" in evidence[0]
