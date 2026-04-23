from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry
from second_brain.habits import Habits
from second_brain.habits.loader import save_habits
from second_brain.habits.schema import DigestHabits
from second_brain.maintain.runner import MaintainRunner


class _FakeReconciliation:
    prefix = "r"
    section = "Reconciliation"

    def __init__(self):
        self.entries = [
            DigestEntry(
                id="",
                section="Reconciliation",
                line="keep clm_a",
                action={"action": "keep", "claim_id": "clm_a"},
            )
        ]

    def run(self, cfg, client):
        return self.entries


@pytest.fixture
def maintain_cfg(tmp_path: Path, monkeypatch) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    (home / "digests").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def test_maintain_without_digest_flag(maintain_cfg: Config) -> None:
    report = MaintainRunner(maintain_cfg).run()
    assert report.digest_entries == 0
    assert report.digest_path is None


def test_maintain_with_digest_runs_builder(maintain_cfg: Config) -> None:
    save_habits(maintain_cfg, Habits(digest=DigestHabits(enabled=True)))

    report = MaintainRunner(maintain_cfg).run(
        build_digest=True,
        digest_passes=[_FakeReconciliation()],
        digest_date=date(2026, 4, 18),
    )
    assert report.digest_entries == 1
    assert report.digest_path is not None
    assert Path(report.digest_path).exists()
    sidecar = Path(report.digest_path).with_suffix(".actions.jsonl")
    assert sidecar.exists()


def test_maintain_digest_disabled_in_habits_short_circuits(maintain_cfg: Config) -> None:
    save_habits(maintain_cfg, Habits(digest=DigestHabits(enabled=False)))
    report = MaintainRunner(maintain_cfg).run(
        build_digest=True,
        digest_passes=[_FakeReconciliation()],
        digest_date=date(2026, 4, 18),
    )
    assert report.digest_entries == 0
    assert report.digest_path is None
