"""Tests for ConfigsBuilder."""
from __future__ import annotations

from pathlib import Path

from app.integrity.plugins.config_registry.builders.configs import (
    ConfigsBuilder,
)

DEFAULT_GLOBS = [
    "pyproject.toml",
    "package.json",
    ".claude/settings.json",
    "vite.config.*",
    "tsconfig*.json",
    "Dockerfile*",
    "Makefile",
    ".env.example",
    "config/integrity.yaml",
]


def test_detects_all_well_known_configs(tiny_repo: Path) -> None:
    builder = ConfigsBuilder(
        repo_root=tiny_repo,
        globs=DEFAULT_GLOBS,
        excluded=["node_modules/**", "**/__pycache__/**"],
    )
    entries, failures = builder.build()
    by_path = {e.path: e for e in entries}
    expected_paths = {
        "pyproject.toml", "package.json", ".claude/settings.json",
        "vite.config.ts", "tsconfig.json", "Dockerfile", "Makefile",
        ".env.example", "config/integrity.yaml",
    }
    assert expected_paths.issubset(set(by_path))
    assert failures == []


def test_type_detection(tiny_repo: Path) -> None:
    builder = ConfigsBuilder(repo_root=tiny_repo, globs=DEFAULT_GLOBS, excluded=[])
    entries, _ = builder.build()
    by_path = {e.path: e for e in entries}
    assert by_path["pyproject.toml"].type == "pyproject"
    assert by_path["package.json"].type == "package_json"
    assert by_path[".claude/settings.json"].type == "claude_settings"
    assert by_path["vite.config.ts"].type == "vite_config"
    assert by_path["tsconfig.json"].type == "tsconfig"
    assert by_path["Dockerfile"].type == "dockerfile"
    assert by_path["Makefile"].type == "makefile"
    assert by_path[".env.example"].type == "env_example"
    assert by_path["config/integrity.yaml"].type == "integrity_yaml"


def test_excluded_glob_skipped(tiny_repo: Path) -> None:
    # Drop a fake config inside an excluded path
    bad = tiny_repo / "node_modules" / "pkg" / "package.json"
    bad.parent.mkdir(parents=True)
    bad.write_text('{"name": "skipped"}\n')

    builder = ConfigsBuilder(
        repo_root=tiny_repo,
        globs=["**/package.json"],
        excluded=["node_modules/**"],
    )
    entries, _ = builder.build()
    paths = [e.path for e in entries]
    assert "node_modules/pkg/package.json" not in paths


def test_each_entry_has_sha(tiny_repo: Path) -> None:
    builder = ConfigsBuilder(repo_root=tiny_repo, globs=DEFAULT_GLOBS, excluded=[])
    entries, _ = builder.build()
    for e in entries:
        assert len(e.sha) == 40


def test_unknown_pattern_skipped(tiny_repo: Path) -> None:
    """Files not matching any glob are not listed."""
    (tiny_repo / "RANDOM.md").write_text("hi\n")
    builder = ConfigsBuilder(repo_root=tiny_repo, globs=DEFAULT_GLOBS, excluded=[])
    entries, _ = builder.build()
    paths = {e.path for e in entries}
    assert "RANDOM.md" not in paths
