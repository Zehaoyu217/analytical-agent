"""Tests for app.core.home — CCAGENT_HOME path helpers."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.home import (
    artifacts_db_path,
    artifacts_disk_path,
    config_path,
    cron_path,
    get_ccagent_home,
    sessions_db_path,
    traces_path,
    wiki_root_path,
)


def test_default_home_is_dotccagent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When CCAGENT_HOME is not set, home resolves to ~/.ccagent."""
    monkeypatch.delenv("CCAGENT_HOME", raising=False)
    home = get_ccagent_home()
    expected = Path("~/.ccagent").expanduser().resolve()
    assert home == expected


def test_env_var_overrides_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When CCAGENT_HOME is set, home resolves to that path."""
    custom = tmp_path / "custom_home"
    monkeypatch.setenv("CCAGENT_HOME", str(custom))
    home = get_ccagent_home()
    assert home == custom.resolve()


def test_all_derived_paths_under_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every derived path helper returns a path inside get_ccagent_home()."""
    monkeypatch.setenv("CCAGENT_HOME", str(tmp_path))
    home = get_ccagent_home()
    helpers = [
        sessions_db_path(),
        artifacts_db_path(),
        artifacts_disk_path(),
        wiki_root_path(),
        traces_path(),
        config_path(),
        cron_path(),
    ]
    for path in helpers:
        assert str(path).startswith(str(home)), (
            f"{path} should be inside {home}"
        )


def test_home_dir_created_on_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_ccagent_home() creates the directory if it does not exist yet."""
    new_dir = tmp_path / "brand_new" / "nested"
    assert not new_dir.exists()
    monkeypatch.setenv("CCAGENT_HOME", str(new_dir))
    home = get_ccagent_home()
    assert home.exists()
    assert home.is_dir()
