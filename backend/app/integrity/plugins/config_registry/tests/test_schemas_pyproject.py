"""Tests for pyproject schema validator."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.config_registry.schemas.pyproject import (
    PyprojectSchema,
)


def test_valid_pyproject(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "x"\nversion = "0.1"\n')
    failures = PyprojectSchema().validate(p, p.read_text())
    assert failures == []


def test_missing_project_table(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[other]\nname = "x"\n')
    failures = PyprojectSchema().validate(p, p.read_text())
    assert any(f.rule == "missing_field" and "[project]" in f.location for f in failures)


def test_missing_name(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nversion = "0.1"\n')
    failures = PyprojectSchema().validate(p, p.read_text())
    assert any(f.location == "[project].name" for f in failures)


def test_missing_version(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "x"\n')
    failures = PyprojectSchema().validate(p, p.read_text())
    assert any(f.location == "[project].version" for f in failures)


def test_malformed_toml(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[project\nname = "x"\n')
    failures = PyprojectSchema().validate(p, p.read_text())
    assert any(f.rule == "parse_error" for f in failures)
