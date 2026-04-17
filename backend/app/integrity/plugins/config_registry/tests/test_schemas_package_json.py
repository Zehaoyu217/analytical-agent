"""Tests for package_json schema validator."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.config_registry.schemas.package_json import (
    PackageJsonSchema,
)


def test_valid(tmp_path: Path) -> None:
    p = tmp_path / "package.json"
    p.write_text('{"name": "x", "version": "0.1.0", "scripts": {}, "dependencies": {}}')
    failures = PackageJsonSchema().validate(p, p.read_text())
    assert failures == []


def test_missing_name(tmp_path: Path) -> None:
    p = tmp_path / "package.json"
    p.write_text('{"version": "0.1.0"}')
    failures = PackageJsonSchema().validate(p, p.read_text())
    assert any(f.location == "name" for f in failures)


def test_scripts_not_object(tmp_path: Path) -> None:
    p = tmp_path / "package.json"
    p.write_text('{"name": "x", "version": "0.1.0", "scripts": []}')
    failures = PackageJsonSchema().validate(p, p.read_text())
    assert any(f.location == "scripts" for f in failures)


def test_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "package.json"
    p.write_text('{not json}')
    failures = PackageJsonSchema().validate(p, p.read_text())
    assert any(f.rule == "parse_error" for f in failures)
