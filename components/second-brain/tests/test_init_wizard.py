from __future__ import annotations

from pathlib import Path

from second_brain.config import Config


def test_config_exposes_readme_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path / "sb"))
    cfg = Config.load()
    assert cfg.readme_path == Path(str(tmp_path / "sb")) / "README.md"


def test_init_wizard_package_importable():
    from second_brain import init_wizard  # noqa: F401
