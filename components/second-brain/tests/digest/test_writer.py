from __future__ import annotations

import json
from datetime import date

from second_brain.digest.schema import DigestEntry
from second_brain.digest.writer import render_actions_jsonl, render_markdown


def _e(id_: str, section: str, line: str, action: dict) -> DigestEntry:
    return DigestEntry(id=id_, section=section, line=line, action=action)


def test_render_markdown_groups_by_section_in_fixed_order() -> None:
    entries = [
        _e("t01", "Taxonomy drift", "new root?", {"action": "add_taxonomy_root", "root": "papers/security"}),
        _e("r01", "Reconciliation", "upgrade clm_a?", {"action": "upgrade_confidence", "claim_id": "clm_a"}),
        _e("e01", "Edge audit", "drop edge?", {"action": "drop_edge", "src_id": "clm_b", "dst_id": "clm_c"}),
    ]
    md = render_markdown(date(2026, 4, 18), entries)
    assert md.startswith("# Digest 2026-04-18\n")
    # Reconciliation appears before Taxonomy drift which appears before Edge audit.
    recon_idx = md.index("## Reconciliation")
    tax_idx = md.index("## Taxonomy drift")
    edge_idx = md.index("## Edge audit")
    assert recon_idx < tax_idx < edge_idx
    assert "- [r01] upgrade clm_a?" in md
    assert "- [t01] new root?" in md
    assert "- [e01] drop edge?" in md


def test_render_markdown_empty_entries_returns_header_only() -> None:
    md = render_markdown(date(2026, 4, 18), [])
    assert md == "# Digest 2026-04-18\n"


def test_render_markdown_omits_empty_sections() -> None:
    entries = [
        _e("r01", "Reconciliation", "k", {"action": "keep", "claim_id": "clm_a"}),
    ]
    md = render_markdown(date(2026, 4, 18), entries)
    assert "## Reconciliation" in md
    assert "## Taxonomy drift" not in md
    assert "## Stale review" not in md


def test_render_actions_jsonl_one_line_per_entry() -> None:
    entries = [
        _e("r01", "Reconciliation", "k", {"action": "keep", "claim_id": "clm_a"}),
        _e("t01", "Taxonomy drift", "t", {"action": "add_taxonomy_root", "root": "papers/sec"}),
    ]
    out = render_actions_jsonl(entries)
    lines = out.rstrip("\n").splitlines()
    assert len(lines) == 2
    row0 = json.loads(lines[0])
    assert row0["id"] == "r01"
    assert row0["section"] == "Reconciliation"
    assert row0["action"] == {"action": "keep", "claim_id": "clm_a"}
    row1 = json.loads(lines[1])
    assert row1["id"] == "t01"


def test_render_actions_jsonl_empty_entries_returns_empty_string() -> None:
    assert render_actions_jsonl([]) == ""
