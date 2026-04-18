"""Tests for :mod:`app.telemetry.skills_log`."""
from __future__ import annotations

import json
from pathlib import Path

from app.telemetry.skills_log import append_skill_event


def test_append_writes_newline_delimited(tmp_path: Path) -> None:
    target = tmp_path / "skills.jsonl"
    append_skill_event(
        {"actor": "skill:foo", "outcome": "ok"}, override_path=target
    )
    append_skill_event(
        {"actor": "skill:bar", "outcome": "error"}, override_path=target
    )
    lines = target.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["actor"] == "skill:foo"
    assert json.loads(lines[1])["outcome"] == "error"


def test_append_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "skills.jsonl"
    append_skill_event({"actor": "skill:x"}, override_path=target)
    assert target.exists()


def test_append_swallows_errors(tmp_path: Path) -> None:
    # A path whose parent is actually a file — mkdir will fail, but the
    # helper must never raise.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("i am a file")
    bad = blocker / "skills.jsonl"
    append_skill_event({"actor": "skill:x"}, override_path=bad)
    # No exception = pass.
