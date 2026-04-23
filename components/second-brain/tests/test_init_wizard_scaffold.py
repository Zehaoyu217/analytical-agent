from __future__ import annotations

from second_brain.config import Config
from second_brain.init_wizard.scaffold import ScaffoldResult, create_tree


def test_create_tree_creates_all_expected_dirs(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()

    result = create_tree(cfg)

    assert isinstance(result, ScaffoldResult)
    assert cfg.sources_dir.is_dir()
    assert cfg.claims_dir.is_dir()
    assert cfg.inbox_dir.is_dir()
    assert cfg.sb_dir.is_dir()
    assert cfg.proposals_dir.is_dir()
    assert cfg.log_path.is_file()
    assert cfg.readme_path.is_file()
    assert "second-brain" in cfg.readme_path.read_text().lower()
    assert result.created_dirs >= 5
    assert result.created_files >= 2


def test_create_tree_is_idempotent(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    # Seed with a non-default readme; re-running must preserve it.
    create_tree(cfg)
    cfg.readme_path.write_text("custom user readme", encoding="utf-8")

    result = create_tree(cfg)
    assert cfg.readme_path.read_text() == "custom user readme"
    # Second call should report zero new files because everything already exists.
    assert result.created_files == 0
