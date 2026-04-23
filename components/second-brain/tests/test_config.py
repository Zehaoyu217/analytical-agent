from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config


def test_resolves_home_from_env(sb_home: Path) -> None:
    cfg = Config.load()
    assert cfg.home == sb_home
    assert cfg.sb_dir == sb_home / ".sb"


def test_default_home_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECOND_BRAIN_HOME", raising=False)
    cfg = Config.load()
    assert cfg.home == Path.home() / "second-brain"


def test_enabled_false_when_sb_dir_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "bare"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    assert cfg.enabled is False


def test_enabled_true_when_both_exist(sb_home: Path) -> None:
    cfg = Config.load()
    assert cfg.enabled is True


def test_digests_dir_under_home(sb_home: Path) -> None:
    cfg = Config.load()
    assert cfg.digests_dir == sb_home / "digests"
