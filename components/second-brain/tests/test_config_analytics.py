from pathlib import Path

from second_brain.config import Config


def test_analytics_path_under_sb_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    cfg = Config.load()
    assert cfg.analytics_path == tmp_path / ".sb" / "analytics.duckdb"


def test_proposals_dir_under_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    cfg = Config.load()
    assert cfg.proposals_dir == tmp_path / "proposals"
