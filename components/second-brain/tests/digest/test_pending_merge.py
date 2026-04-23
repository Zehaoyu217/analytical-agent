"""Tests for ``second_brain.digest.pending`` (read/truncate/merge)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from second_brain.digest.pending import merge_pending, read_pending, truncate_pending
from second_brain.digest.schema import DigestEntry


@dataclass
class FakeCfg:
    digests_dir: Path


def _write_pending(digests: Path, records: list[dict]) -> Path:
    pending = digests / "pending.jsonl"
    pending.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return pending


def test_read_pending_parses_records_without_truncating(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    pending = _write_pending(
        digests,
        [
            {
                "id": "pend_0001",
                "section": "Reconciliation",
                "action": {"action": "keep", "rationale": "keep as-is"},
                "proposed_at": "2026-04-18T00:00:00Z",
            }
        ],
    )

    proposals = read_pending(FakeCfg(digests_dir=digests))

    assert len(proposals) == 1
    assert proposals[0].id == "pend_0001"
    assert proposals[0].section == "Reconciliation"
    assert proposals[0].line == "keep as-is"
    assert proposals[0].action == {"action": "keep", "rationale": "keep as-is"}
    # Critical: read_pending must NOT mutate the file.
    assert pending.read_text().strip() != ""


def test_read_pending_returns_empty_when_file_missing(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    assert read_pending(FakeCfg(digests_dir=digests)) == []


def test_read_pending_skips_malformed_lines(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    pending = digests / "pending.jsonl"
    pending.write_text(
        "\n".join(
            [
                "not-json",
                json.dumps(
                    {
                        "id": "pend_0002",
                        "section": "Taxonomy",
                        "action": {"action": "add_taxonomy_root", "root": "papers/x"},
                    }
                ),
                "",
                "{broken json",
            ]
        )
        + "\n"
    )

    proposals = read_pending(FakeCfg(digests_dir=digests))
    assert len(proposals) == 1
    assert proposals[0].id == "pend_0002"
    assert proposals[0].section == "Taxonomy"
    assert proposals[0].line == "add_taxonomy_root"


def test_read_pending_line_falls_back_to_action_name_when_no_rationale(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    _write_pending(
        digests,
        [
            {
                "id": "pend_0003",
                "section": "Reconciliation",
                "action": {"action": "upgrade_confidence", "claim_id": "clm_x"},
            }
        ],
    )
    proposals = read_pending(FakeCfg(digests_dir=digests))
    assert proposals[0].line == "upgrade_confidence"


def test_read_pending_tolerates_missing_action_key(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "pending.jsonl").write_text(
        json.dumps({"id": "pend_0004", "section": "Misc"}) + "\n"
    )
    proposals = read_pending(FakeCfg(digests_dir=digests))
    assert proposals[0].action == {}
    assert proposals[0].line == ""


def test_truncate_pending_clears_file(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    pending = digests / "pending.jsonl"
    pending.write_text("whatever\n")

    truncate_pending(FakeCfg(digests_dir=digests))

    assert pending.read_text() == ""


def test_truncate_pending_is_safe_when_file_missing(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    truncate_pending(FakeCfg(digests_dir=digests))  # should not raise
    assert not (digests / "pending.jsonl").exists()


def test_merge_pending_legacy_helper_still_works(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    pending = _write_pending(
        digests,
        [{"id": "pend_x", "section": "Taxonomy", "action": {"action": "keep"}}],
    )
    existing = [DigestEntry(id="r01", section="R", line="l", action={"action": "keep"})]

    merged = merge_pending(FakeCfg(digests_dir=digests), existing)

    assert len(merged) == 2
    assert merged[1].id == "pend_x"
    # Backward-compat: the legacy helper still truncates.
    assert pending.read_text() == ""
    # Immutability: returns a new list.
    assert merged is not existing
