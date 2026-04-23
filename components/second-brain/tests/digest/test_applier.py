from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.digest.applier import ApplyResult, DigestApplier
from second_brain.digest.schema import DigestEntry


def _write_sidecar(cfg: Config, d, entries: list[DigestEntry]) -> Path:
    sidecar = cfg.digests_dir / f"{d.isoformat()}.actions.jsonl"
    sidecar.write_text(
        "\n".join(
            json.dumps({"id": e.id, "section": e.section, "action": e.action})
            for e in entries
        )
        + "\n",
        encoding="utf-8",
    )
    return sidecar


def test_apply_upgrade_confidence(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a", confidence="low")
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="r01",
        section="Reconciliation",
        line="upgrade clm_a?",
        action={"action": "upgrade_confidence", "claim_id": "clm_a", "from": "low", "to": "medium", "rationale": "solid refs"},
    )
    _write_sidecar(digest_cfg, d, [entry])

    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    assert result.applied == ["r01"]
    assert result.failed == []
    text = (digest_cfg.claims_dir / "clm_a.md").read_text(encoding="utf-8")
    assert "confidence: medium" in text


def test_apply_keep_is_noop(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a")
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="r01",
        section="Reconciliation",
        line="keep",
        action={"action": "keep", "claim_id": "clm_a", "rationale": "fine"},
    )
    _write_sidecar(digest_cfg, d, [entry])
    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    assert result.applied == ["r01"]


def test_apply_resolve_contradiction_writes_resolution_file(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a", contradicts=["clm_b"])
    write_claim(digest_cfg, "clm_b", contradicts=["clm_a"])
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="r01",
        section="Reconciliation",
        line="resolve?",
        action={
            "action": "resolve_contradiction",
            "left_id": "clm_a",
            "right_id": "clm_b",
            "rationale": "A superior empirically",
        },
    )
    _write_sidecar(digest_cfg, d, [entry])

    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids=["r01"])
    assert result.applied == ["r01"]
    res_file = digest_cfg.claims_dir / "resolutions" / "clm_a__vs__clm_b.md"
    assert res_file.exists()
    assert "A superior empirically" in res_file.read_text(encoding="utf-8")


def test_apply_promote_wiki_to_claim(digest_cfg: Config, tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    finding = wiki / "finding.md"
    finding.write_text(
        "---\nstatus: mature\ntaxonomy: papers/ml\n---\nBody of finding.\n",
        encoding="utf-8",
    )
    import os
    os.environ["SB_WIKI_DIR"] = str(wiki)
    try:
        d = datetime.now(UTC).date()
        entry = DigestEntry(
            id="w01",
            section="Wiki ↔ KB drift",
            line="promote?",
            action={
                "action": "promote_wiki_to_claim",
                "wiki_path": "finding.md",
                "proposed_taxonomy": "papers/ml",
            },
        )
        _write_sidecar(digest_cfg, d, [entry])
        result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
        assert result.applied == ["w01"]
        # Applier should write a stub claim file under claims/.
        written = list(digest_cfg.claims_dir.glob("clm_*.md"))
        assert len(written) == 1
        assert "finding.md" in written[0].read_text(encoding="utf-8")
    finally:
        os.environ.pop("SB_WIKI_DIR", None)


def test_apply_backlink_claim_to_wiki(digest_cfg: Config, tmp_path: Path, write_claim) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    finding = wiki / "note.md"
    finding.write_text("Body\n", encoding="utf-8")
    import os
    os.environ["SB_WIKI_DIR"] = str(wiki)
    try:
        write_claim(digest_cfg, "clm_a")
        d = datetime.now(UTC).date()
        entry = DigestEntry(
            id="w01",
            section="Wiki ↔ KB drift",
            line="backlink?",
            action={"action": "backlink_claim_to_wiki", "claim_id": "clm_a", "wiki_path": "note.md"},
        )
        _write_sidecar(digest_cfg, d, [entry])
        result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
        assert result.applied == ["w01"]
        assert "clm_a" in (wiki / "note.md").read_text(encoding="utf-8")
    finally:
        os.environ.pop("SB_WIKI_DIR", None)


def test_apply_add_taxonomy_root_appends_to_habits(digest_cfg: Config) -> None:
    from second_brain.habits import Habits
    from second_brain.habits.loader import load_habits, save_habits

    save_habits(digest_cfg, Habits.default())
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="t01",
        section="Taxonomy drift",
        line="add?",
        action={"action": "add_taxonomy_root", "root": "papers/security", "example_claim_ids": []},
    )
    _write_sidecar(digest_cfg, d, [entry])
    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    assert result.applied == ["t01"]
    reloaded = load_habits(digest_cfg)
    assert "papers/security" in reloaded.taxonomy.roots


def test_apply_re_abstract_batch_marks_claims(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a")
    write_claim(digest_cfg, "clm_b")
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="s01",
        section="Stale review",
        line="re-abstract?",
        action={"action": "re_abstract_batch", "claim_ids": ["clm_a", "clm_b"], "taxonomy": "papers/ml/*"},
    )
    _write_sidecar(digest_cfg, d, [entry])
    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    assert result.applied == ["s01"]
    for cid in ("clm_a", "clm_b"):
        text = (digest_cfg.claims_dir / f"{cid}.md").read_text(encoding="utf-8")
        assert "needs_reabstract: true" in text


def test_apply_drop_edge_removes_target_from_frontmatter(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a", contradicts=["clm_x"])
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="e01",
        section="Edge audit",
        line="drop edge?",
        action={"action": "drop_edge", "src_id": "clm_a", "dst_id": "clm_x", "relation": "contradicts"},
    )
    _write_sidecar(digest_cfg, d, [entry])
    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    assert result.applied == ["e01"]
    text = (digest_cfg.claims_dir / "clm_a.md").read_text(encoding="utf-8")
    assert "clm_x" not in text


def test_apply_writes_applied_jsonl_sidecar(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a", confidence="low")
    d = datetime.now(UTC).date()
    entry = DigestEntry(
        id="r01",
        section="Reconciliation",
        line="upgrade?",
        action={"action": "upgrade_confidence", "claim_id": "clm_a", "from": "low", "to": "medium", "rationale": ""},
    )
    _write_sidecar(digest_cfg, d, [entry])
    DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    applied = digest_cfg.digests_dir / f"{d.isoformat()}.applied.jsonl"
    assert applied.exists()
    row = json.loads(applied.read_text(encoding="utf-8").strip())
    assert row["id"] == "r01"
    assert "applied_at" in row


def test_apply_failing_handler_isolates_entry(digest_cfg: Config) -> None:
    # No claim file for clm_missing — upgrade_confidence handler should fail.
    d = datetime.now(UTC).date()
    entries = [
        DigestEntry(
            id="r01",
            section="Reconciliation",
            line="bad",
            action={"action": "upgrade_confidence", "claim_id": "clm_missing", "from": "low", "to": "medium", "rationale": ""},
        ),
        DigestEntry(
            id="t01",
            section="Taxonomy drift",
            line="ok",
            action={"action": "add_taxonomy_root", "root": "papers/sec", "example_claim_ids": []},
        ),
    ]
    _write_sidecar(digest_cfg, d, entries)
    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids="all")
    assert "t01" in result.applied
    assert any(fid == "r01" for fid, _ in result.failed)


def test_apply_filters_by_entry_ids(digest_cfg: Config, write_claim) -> None:
    write_claim(digest_cfg, "clm_a", confidence="low")
    write_claim(digest_cfg, "clm_b", confidence="low")
    d = datetime.now(UTC).date()
    entries = [
        DigestEntry(
            id="r01",
            section="Reconciliation",
            line="a",
            action={"action": "upgrade_confidence", "claim_id": "clm_a", "from": "low", "to": "medium", "rationale": ""},
        ),
        DigestEntry(
            id="r02",
            section="Reconciliation",
            line="b",
            action={"action": "upgrade_confidence", "claim_id": "clm_b", "from": "low", "to": "medium", "rationale": ""},
        ),
    ]
    _write_sidecar(digest_cfg, d, entries)
    result = DigestApplier(digest_cfg).apply(digest_date=d, entry_ids=["r01"])
    assert result.applied == ["r01"]
    assert "r02" in result.skipped
    assert "confidence: medium" in (digest_cfg.claims_dir / "clm_a.md").read_text()
    assert "confidence: low" in (digest_cfg.claims_dir / "clm_b.md").read_text()
