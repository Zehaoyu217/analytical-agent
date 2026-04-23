from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.inbox.runner import InboxRunner


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_inbox_runner_ingests_note_and_moves_to_processed(sb_home: Path):
    note = sb_home / "inbox" / "idea.md"
    note.write_text("# Idea\n\nA test note.\n", encoding="utf-8")

    cfg = Config.load()
    result = InboxRunner(cfg).run()

    assert len(result.ok) == 1
    assert result.failed == []
    # Original moved under .processed/<date>/idea.md
    assert not note.exists()
    processed = list((sb_home / "inbox" / ".processed").rglob("idea.md"))
    assert len(processed) == 1
    # Source folder exists
    assert any((sb_home / "sources").iterdir())
    # Manifest written
    manifest = (sb_home / ".sb" / "inbox_manifest.json")
    assert manifest.exists()


def test_inbox_runner_failed_item_stays_in_inbox_and_records_error(sb_home: Path, monkeypatch: pytest.MonkeyPatch):
    bad = sb_home / "inbox" / "bad.xyz"
    bad.write_bytes(b"not ingestable")

    cfg = Config.load()
    result = InboxRunner(cfg).run()

    assert result.ok == []
    assert len(result.failed) == 1
    assert bad.exists(), "failed file must stay in inbox for manual triage"
    manifest = (sb_home / ".sb" / "inbox_manifest.json").read_text()
    assert "bad.xyz" in manifest
    assert "failed" in manifest


def test_inbox_runner_skips_dotfiles(sb_home: Path):
    (sb_home / "inbox" / ".DS_Store").write_text("noise")
    cfg = Config.load()
    result = InboxRunner(cfg).run()
    assert result.ok == []
    assert result.failed == []


def test_inbox_runner_caps_retry_attempts_at_3(sb_home: Path):
    """After 3 failed attempts across separate runs, item is marked quarantined."""
    bad = sb_home / "inbox" / "bad.xyz"
    bad.write_bytes(b"not ingestable")
    cfg = Config.load()
    for _ in range(4):
        InboxRunner(cfg).run()
    manifest = (sb_home / ".sb" / "inbox_manifest.json").read_text()
    # Last run should record quarantined=True once attempts>=3
    assert "quarantined" in manifest
