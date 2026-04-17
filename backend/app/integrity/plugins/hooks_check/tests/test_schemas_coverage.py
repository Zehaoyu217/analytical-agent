"""Tests for CoverageSchemaValidator (mirrors Plugin E schema test pattern)."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.hooks_check.schemas.coverage import (
    CoverageSchemaValidator,
)


def test_valid_doc_produces_no_failures(tmp_path: Path) -> None:
    p = tmp_path / "hooks_coverage.yaml"
    body = (
        "rules:\n"
        "  - id: a\n"
        "    description: x\n"
        "    when: {paths: ['*.py']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write', command_substring: x}\n"
        "tolerated: []\n"
    )
    p.write_text(body)
    failures = CoverageSchemaValidator().validate(p, body)
    assert failures == []


def test_invalid_yaml_returns_parse_error(tmp_path: Path) -> None:
    p = tmp_path / "hooks_coverage.yaml"
    body = "rules:\n  - id: [unclosed\n"
    p.write_text(body)
    failures = CoverageSchemaValidator().validate(p, body)
    assert len(failures) == 1
    assert failures[0].rule == "parse_error"


def test_missing_rules_returns_failure(tmp_path: Path) -> None:
    p = tmp_path / "hooks_coverage.yaml"
    body = "tolerated: []\n"
    p.write_text(body)
    failures = CoverageSchemaValidator().validate(p, body)
    assert any(f.rule == "missing_field" and "rules" in f.location for f in failures)


def test_rule_missing_required_field(tmp_path: Path) -> None:
    p = tmp_path / "hooks_coverage.yaml"
    body = (
        "rules:\n"
        "  - id: a\n"
        "    description: x\n"
        "    when: {paths: ['*.py']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write'}\n"
    )
    p.write_text(body)
    failures = CoverageSchemaValidator().validate(p, body)
    assert any(
        f.rule == "missing_field"
        and "command_substring" in f.location
        for f in failures
    )


def test_type_name_constant() -> None:
    assert CoverageSchemaValidator().type_name == "hooks_coverage"
