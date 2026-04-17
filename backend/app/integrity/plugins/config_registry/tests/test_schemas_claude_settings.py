"""Tests for claude_settings schema validator."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.config_registry.schemas.claude_settings import (
    ClaudeSettingsSchema,
)


def test_valid_with_hooks(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text('{"hooks": {"PostToolUse": [{"matcher": "Edit", "command": "echo"}]}}')
    failures = ClaudeSettingsSchema().validate(p, p.read_text())
    assert failures == []


def test_valid_without_hooks(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text('{}')
    failures = ClaudeSettingsSchema().validate(p, p.read_text())
    assert failures == []


def test_hooks_malformed(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text('{"hooks": {"PostToolUse": [{"matcher": "Edit"}]}}')  # no command
    failures = ClaudeSettingsSchema().validate(p, p.read_text())
    assert any("command" in f.location for f in failures)


def test_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text('{x}')
    failures = ClaudeSettingsSchema().validate(p, p.read_text())
    assert any(f.rule == "parse_error" for f in failures)
