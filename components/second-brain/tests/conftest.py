from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolated SECOND_BRAIN_HOME for the duration of the test."""
    home = tmp_path / "second-brain"
    home.mkdir()
    (home / ".sb").mkdir()
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    (home / "inbox").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    yield home
