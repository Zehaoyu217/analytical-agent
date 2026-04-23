"""Integration test — DigestBuilder absorbs digests/pending.jsonl proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from second_brain.config import Config
from second_brain.digest.builder import DigestBuilder
from second_brain.digest.schema import DigestEntry
from second_brain.habits import Habits
from second_brain.habits.schema import DigestHabits


@dataclass
class FakePass:
    prefix: str
    section: str
    entries: list[DigestEntry]

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        return list(self.entries)


def _habits() -> Habits:
    return Habits(
        digest=DigestHabits(
            enabled=True,
            passes={
                "reconciliation": True,
                "wiki_bridge": True,
                "taxonomy_drift": True,
                "stale_review": True,
                "edge_audit": True,
            },
            min_entries_to_emit=0,
        )
    )


def test_builder_merges_pending_and_truncates_file(digest_cfg: Config) -> None:
    """Seed pending.jsonl, run builder, assert proposal appears and file is empty."""
    pending_path = digest_cfg.digests_dir / "pending.jsonl"
    pending_path.write_text(
        json.dumps(
            {
                "id": "pend_0001",
                "section": "Reconciliation",
                "action": {"action": "keep", "rationale": "agent says keep"},
                "proposed_at": "2026-04-18T00:00:00Z",
            }
        )
        + "\n"
    )

    recon = FakePass(
        prefix="r",
        section="Reconciliation",
        entries=[
            DigestEntry(
                id="",
                section="Reconciliation",
                line="native entry",
                action={"action": "keep", "claim_id": "clm_a"},
            ),
        ],
    )
    builder = DigestBuilder(digest_cfg, habits=_habits(), passes=[recon])

    result = builder.build(today=date(2026, 4, 18))

    ids = [e.id for e in result.entries]
    assert "r01" in ids
    assert "pend_0001" in ids

    proposed = next(e for e in result.entries if e.id == "pend_0001")
    assert proposed.section == "Reconciliation"
    assert proposed.action == {"action": "keep", "rationale": "agent says keep"}

    # Written to the jsonl envelope too.
    jsonl_lines = [
        json.loads(ln) for ln in result.actions_jsonl.strip().splitlines() if ln.strip()
    ]
    assert any(row["id"] == "pend_0001" for row in jsonl_lines)

    # pending.jsonl truncated on success so proposals don't double-land.
    assert pending_path.exists()
    assert pending_path.read_text() == ""


def test_builder_is_noop_when_pending_missing(digest_cfg: Config) -> None:
    recon = FakePass(
        prefix="r",
        section="Reconciliation",
        entries=[
            DigestEntry(
                id="",
                section="Reconciliation",
                line="only native",
                action={"action": "keep", "claim_id": "clm_a"},
            ),
        ],
    )
    builder = DigestBuilder(digest_cfg, habits=_habits(), passes=[recon])
    result = builder.build(today=date(2026, 4, 18))

    assert [e.id for e in result.entries] == ["r01"]
    assert not (digest_cfg.digests_dir / "pending.jsonl").exists()


def test_builder_preserves_pending_when_below_min_entries_gate(digest_cfg: Config) -> None:
    """Regression: empty passes + one proposal below threshold must NOT drop the proposal.

    Previously ``merge_pending`` truncated the file before the min-entries
    gate, so a sub-threshold build would silently wipe pending proposals. The
    read/truncate split keeps them on disk until a build actually emits.
    """
    pending_path = digest_cfg.digests_dir / "pending.jsonl"
    original = (
        json.dumps(
            {
                "id": "pend_keep_me",
                "section": "Reconciliation",
                "action": {"action": "keep"},
            }
        )
        + "\n"
    )
    pending_path.write_text(original)

    habits = Habits(
        digest=DigestHabits(
            enabled=True,
            passes={k: True for k in
                    ("reconciliation", "wiki_bridge", "taxonomy_drift",
                     "stale_review", "edge_audit")},
            min_entries_to_emit=5,  # one proposal, zero pass output → below gate
        )
    )
    builder = DigestBuilder(digest_cfg, habits=habits, passes=[])  # no passes

    result = builder.build(today=date(2026, 4, 18))

    assert result.entries == []
    # Critical: file must still contain the proposal for the next build.
    assert pending_path.read_text() == original
