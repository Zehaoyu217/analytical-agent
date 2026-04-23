from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from second_brain.config import Config
from second_brain.digest.builder import BuildResult, DigestBuilder
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


def _habits(
    enabled: bool = True,
    min_entries: int = 0,
    passes_on: tuple[str, ...] = (
        "reconciliation",
        "wiki_bridge",
        "taxonomy_drift",
        "stale_review",
        "edge_audit",
    ),
) -> Habits:
    return Habits(
        digest=DigestHabits(
            enabled=enabled,
            passes={
                "reconciliation": "reconciliation" in passes_on,
                "wiki_bridge": "wiki_bridge" in passes_on,
                "taxonomy_drift": "taxonomy_drift" in passes_on,
                "stale_review": "stale_review" in passes_on,
                "edge_audit": "edge_audit" in passes_on,
            },
            min_entries_to_emit=min_entries,
        )
    )


def test_builder_rewrites_ids_in_deterministic_order(digest_cfg: Config) -> None:
    recon = FakePass(
        prefix="r",
        section="Reconciliation",
        entries=[
            DigestEntry(id="", section="Reconciliation", line="zeta", action={"action": "keep", "claim_id": "clm_z"}),
            DigestEntry(id="", section="Reconciliation", line="alpha", action={"action": "keep", "claim_id": "clm_a"}),
        ],
    )
    tax = FakePass(
        prefix="t",
        section="Taxonomy drift",
        entries=[
            DigestEntry(
                id="",
                section="Taxonomy drift",
                line="papers/security cluster",
                action={"action": "add_taxonomy_root", "root": "papers/security"},
            )
        ],
    )
    builder = DigestBuilder(digest_cfg, habits=_habits(), passes=[recon, tax])
    result = builder.build(today=date(2026, 4, 18))

    assert isinstance(result, BuildResult)
    # Deterministic order by primary target; ids rewritten
    ids = [e.id for e in result.entries]
    assert ids == ["r01", "r02", "t01"]
    # r01 is for clm_a (alpha), r02 for clm_z — sorted by primary key
    assert result.entries[0].action["claim_id"] == "clm_a"
    assert result.entries[1].action["claim_id"] == "clm_z"
    assert result.entries[2].action["action"] == "add_taxonomy_root"

    # actions_jsonl shape
    lines = result.actions_jsonl.strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first["id"] == "r01"
    assert first["action"] == {"action": "keep", "claim_id": "clm_a"}
    assert first["section"] == "Reconciliation"


def test_builder_respects_disabled_passes(digest_cfg: Config) -> None:
    recon = FakePass(
        prefix="r",
        section="Reconciliation",
        entries=[DigestEntry(id="", section="Reconciliation", line="k", action={"action": "keep", "claim_id": "clm_a"})],
    )
    tax = FakePass(
        prefix="t",
        section="Taxonomy drift",
        entries=[DigestEntry(id="", section="Taxonomy drift", line="t", action={"action": "add_taxonomy_root", "root": "papers/security"})],
    )
    habits = _habits(passes_on=("reconciliation",))  # taxonomy disabled
    builder = DigestBuilder(digest_cfg, habits=habits, passes=[recon, tax])
    result = builder.build(today=date(2026, 4, 18))
    assert [e.id for e in result.entries] == ["r01"]


def test_builder_min_entries_short_circuits(digest_cfg: Config) -> None:
    recon = FakePass(
        prefix="r",
        section="Reconciliation",
        entries=[DigestEntry(id="", section="Reconciliation", line="k", action={"action": "keep", "claim_id": "clm_a"})],
    )
    habits = _habits(min_entries=5)
    builder = DigestBuilder(digest_cfg, habits=habits, passes=[recon])
    result = builder.build(today=date(2026, 4, 18))
    assert result.entries == []
    assert result.actions_jsonl == ""
    assert result.markdown == ""


def test_builder_applies_skip_filter(digest_cfg: Config) -> None:
    from second_brain.digest.skip import SkipRegistry

    entry = DigestEntry(
        id="",
        section="Reconciliation",
        line="keep claim",
        action={"action": "keep", "claim_id": "clm_a"},
    )
    # Pre-register a skip for this signature
    reg = SkipRegistry(digest_cfg)
    reg.skip_signature(
        reg.signature(entry),
        today=date(2026, 4, 18),
        ttl_days=7,
    )

    recon = FakePass(prefix="r", section="Reconciliation", entries=[entry])
    builder = DigestBuilder(digest_cfg, habits=_habits(), passes=[recon])
    result = builder.build(today=date(2026, 4, 18))
    assert result.entries == []


def test_builder_expired_skip_does_not_filter(digest_cfg: Config) -> None:
    from second_brain.digest.skip import SkipRegistry

    entry = DigestEntry(
        id="",
        section="Reconciliation",
        line="keep claim",
        action={"action": "keep", "claim_id": "clm_a"},
    )
    reg = SkipRegistry(digest_cfg)
    reg.skip_signature(reg.signature(entry), today=date(2026, 4, 1), ttl_days=7)

    recon = FakePass(prefix="r", section="Reconciliation", entries=[entry])
    builder = DigestBuilder(digest_cfg, habits=_habits(), passes=[recon])
    result = builder.build(today=date(2026, 4, 18))
    assert len(result.entries) == 1
