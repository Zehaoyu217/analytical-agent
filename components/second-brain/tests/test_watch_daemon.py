from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.watch.daemon import Watcher
from second_brain.watch.queue import SerialQueue


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_handler_enqueues_on_created_event(sb_home: Path):
    calls: list[Path] = []
    q = SerialQueue()
    w = Watcher(Config.load(), queue=q, worker=lambda path: calls.append(path), clock=lambda: 0.0)

    # Simulate a watchdog on_created event on a .md file in inbox
    new_file = sb_home / "inbox" / "drop.md"
    new_file.write_text("# x")
    w._handle_event(str(new_file))

    assert q.pending() == 1
    # Drain past debounce
    q.drain_until_empty(now=10.0)
    assert calls == [new_file]


def test_handler_skips_dotfiles_and_directories(sb_home: Path):
    q = SerialQueue()
    w = Watcher(Config.load(), queue=q, worker=lambda p: None, clock=lambda: 0.0)

    dot = sb_home / "inbox" / ".DS_Store"
    dot.write_text("x")
    w._handle_event(str(dot))
    assert q.pending() == 0

    sub = sb_home / "inbox" / ".processed"
    sub.mkdir()
    w._handle_event(str(sub))
    assert q.pending() == 0


def test_handler_dedupes_rapid_events_for_same_path(sb_home: Path):
    calls: list[Path] = []
    q = SerialQueue()
    w = Watcher(Config.load(), queue=q, worker=lambda p: calls.append(p), clock=lambda: 0.0)

    f = sb_home / "inbox" / "thrash.md"
    f.write_text("x")
    for _ in range(5):
        w._handle_event(str(f))

    assert q.pending() == 1
    q.drain_until_empty(now=10.0)
    assert calls == [f]  # exactly once
