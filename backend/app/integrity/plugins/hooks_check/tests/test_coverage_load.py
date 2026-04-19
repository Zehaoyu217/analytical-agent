"""Tests for coverage doc parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.integrity.plugins.hooks_check.coverage import (
    CoverageDoc,
    load_coverage,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "hooks_coverage.yaml"
    p.write_text(body)
    return p


def test_load_minimal(tmp_path: Path) -> None:
    p = _write(tmp_path,
        "rules:\n"
        "  - id: a\n"
        "    description: alpha\n"
        "    when:\n"
        "      paths: ['*.py']\n"
        "    requires_hook:\n"
        "      event: PostToolUse\n"
        "      matcher: 'Write|Edit'\n"
        "      command_substring: ruff\n"
        "tolerated:\n"
        "  - sb inject\n"
    )
    doc = load_coverage(p)
    assert isinstance(doc, CoverageDoc)
    assert len(doc.rules) == 1
    rule = doc.rules[0]
    assert rule.id == "a"
    assert rule.description == "alpha"
    assert rule.when.paths == ("*.py",)
    assert rule.requires_hook.event == "PostToolUse"
    assert rule.requires_hook.matcher == "Write|Edit"
    assert rule.requires_hook.command_substring == "ruff"
    assert doc.tolerated == ("sb inject",)


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_coverage(tmp_path / "missing.yaml")


def test_load_empty_rules_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, "rules: []\ntolerated: []\n")
    with pytest.raises(ValueError, match="at least one rule"):
        load_coverage(p)


def test_load_duplicate_ids_raises(tmp_path: Path) -> None:
    p = _write(tmp_path,
        "rules:\n"
        "  - id: a\n"
        "    description: x\n"
        "    when: {paths: ['*.py']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write', command_substring: x}\n"
        "  - id: a\n"
        "    description: y\n"
        "    when: {paths: ['*.md']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write', command_substring: y}\n"
    )
    with pytest.raises(ValueError, match="duplicate rule id"):
        load_coverage(p)


def test_load_missing_required_field_raises(tmp_path: Path) -> None:
    p = _write(tmp_path,
        "rules:\n"
        "  - id: a\n"
        "    description: x\n"
        "    when: {paths: ['*.py']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write'}\n"
    )
    with pytest.raises(ValueError, match="command_substring"):
        load_coverage(p)


def test_load_no_tolerated_defaults_empty(tmp_path: Path) -> None:
    p = _write(tmp_path,
        "rules:\n"
        "  - id: a\n"
        "    description: x\n"
        "    when: {paths: ['*.py']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write', command_substring: x}\n"
    )
    doc = load_coverage(p)
    assert doc.tolerated == ()


def test_load_paths_must_be_nonempty_list(tmp_path: Path) -> None:
    p = _write(tmp_path,
        "rules:\n"
        "  - id: a\n"
        "    description: x\n"
        "    when: {paths: []}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write', command_substring: x}\n"
    )
    with pytest.raises(ValueError, match="paths"):
        load_coverage(p)
