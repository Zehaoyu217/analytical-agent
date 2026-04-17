"""Tests for settings.json parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.integrity.plugins.hooks_check.settings_parser import (
    HookRecord,
    parse_settings,
)


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(payload))
    return p


def test_empty_settings_returns_empty(tmp_path: Path) -> None:
    p = _write(tmp_path, {})
    assert parse_settings(p) == []


def test_no_hooks_key_returns_empty(tmp_path: Path) -> None:
    p = _write(tmp_path, {"otherKey": "value"})
    assert parse_settings(p) == []


def test_single_hook_with_matcher(tmp_path: Path) -> None:
    p = _write(tmp_path, {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {"type": "command", "command": "echo hi"},
                    ],
                },
            ],
        },
    })
    records = parse_settings(p)
    assert len(records) == 1
    assert records[0] == HookRecord(
        event="PostToolUse",
        matcher="Write|Edit",
        command="echo hi",
        source_index=(0, 0, 0),
    )


def test_hook_without_matcher_defaults_to_empty(tmp_path: Path) -> None:
    p = _write(tmp_path, {
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "sb inject"}]},
            ],
        },
    })
    records = parse_settings(p)
    assert records[0].matcher == ""
    assert records[0].command == "sb inject"


def test_multiple_events_and_blocks(tmp_path: Path) -> None:
    p = _write(tmp_path, {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Write", "hooks": [
                    {"type": "command", "command": "a"},
                    {"type": "command", "command": "b"},
                ]},
                {"matcher": "Edit", "hooks": [
                    {"type": "command", "command": "c"},
                ]},
            ],
            "Stop": [
                {"hooks": [{"type": "command", "command": "d"}]},
            ],
        },
    })
    records = parse_settings(p)
    commands = sorted(r.command for r in records)
    assert commands == ["a", "b", "c", "d"]


def test_non_command_hook_type_is_skipped(tmp_path: Path) -> None:
    p = _write(tmp_path, {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Write", "hooks": [
                    {"type": "command", "command": "real"},
                    {"type": "future_type", "config": {}},
                ]},
            ],
        },
    })
    records = parse_settings(p)
    assert [r.command for r in records] == ["real"]


def test_missing_settings_file_returns_empty(tmp_path: Path) -> None:
    assert parse_settings(tmp_path / "absent.json") == []


def test_invalid_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("{not valid json")
    with pytest.raises(ValueError, match="JSON"):
        parse_settings(p)


def test_top_level_not_object_raises(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("[]")
    with pytest.raises(ValueError, match="top-level"):
        parse_settings(p)


def test_hooks_event_must_be_list(tmp_path: Path) -> None:
    p = _write(tmp_path, {"hooks": {"PostToolUse": "not a list"}})
    with pytest.raises(ValueError, match="PostToolUse"):
        parse_settings(p)


def test_inner_hook_missing_command_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Write", "hooks": [{"type": "command"}]},
            ],
        },
    })
    with pytest.raises(ValueError, match="command"):
        parse_settings(p)
