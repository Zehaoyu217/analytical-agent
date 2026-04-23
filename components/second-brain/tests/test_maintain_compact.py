from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.maintain.compact import compact_duckdb, compact_fts
from second_brain.store.fts_store import FtsStore


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_compact_fts_noop_when_db_missing(sb_home: Path):
    cfg = Config.load()
    result = compact_fts(cfg)
    assert result.before == 0
    assert result.after == 0


def test_compact_fts_reduces_or_preserves_size(sb_home: Path):
    cfg = Config.load()
    with FtsStore.open(cfg.fts_path) as store:
        store.ensure_schema()
        for i in range(50):
            store.insert_claim(
                claim_id=f"c{i}", statement=f"stmt {i}", abstract="", body="", taxonomy="x"
            )
    result = compact_fts(cfg)
    assert result.before > 0
    assert result.after <= result.before  # may equal on tiny DB; must not grow


def test_compact_duckdb_noop_when_db_missing(sb_home: Path):
    cfg = Config.load()
    result = compact_duckdb(cfg)
    assert result.before == 0
    assert result.after == 0
