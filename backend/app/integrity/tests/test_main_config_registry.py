"""Tests for __main__.py wiring of config_registry plugin."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.integrity.__main__ import KNOWN_PLUGINS, _build_engine, main


def test_known_plugins_includes_config_registry() -> None:
    assert "config_registry" in KNOWN_PLUGINS


def test_unknown_plugin_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        _build_engine(tmp_path, only="bogus", skip_augment=True)
    assert "bogus" in str(exc.value)


def test_build_engine_only_config_registry(tmp_path: Path) -> None:
    """When run alone, ConfigRegistryPlugin's depends_on remains () — runs fine."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config/integrity.yaml").write_text(
        "plugins:\n  config_registry:\n    enabled: true\n"
        "    manifest_path: config/manifest.yaml\n"
        "    skills_root: backend/app/skills\n"
        "    scripts_root: scripts\n"
        "    config_globs: []\n"
        "    excluded_paths: []\n"
        "    function_search_globs: []\n"
        "    function_decorators: []\n"
        "    function_event_handlers: []\n"
    )
    eng = _build_engine(tmp_path, only="config_registry", skip_augment=True)
    assert any(p.name == "config_registry" for p in eng.plugins)


def test_main_check_flag_accepted(tmp_path: Path, capsys) -> None:
    """`--plugin config_registry --check` parses without error."""
    import json as _json
    (tmp_path / "config").mkdir()
    (tmp_path / "config/integrity.yaml").write_text(
        "plugins:\n  config_registry:\n    enabled: true\n"
        "    manifest_path: config/manifest.yaml\n"
        "    skills_root: skills\n"
        "    scripts_root: scripts\n"
        "    config_globs: []\n"
        "    excluded_paths: []\n"
        "    function_search_globs: []\n"
        "    function_decorators: []\n"
        "    function_event_handlers: []\n"
    )
    (tmp_path / "graphify").mkdir()
    (tmp_path / "graphify" / "graph.json").write_text(_json.dumps({"nodes": [], "links": []}))
    rc = main([
        "--plugin", "config_registry",
        "--check",
        "--repo-root", str(tmp_path),
        "--no-augment",
    ])
    assert rc in (0, 1)  # 0 if matches, 1 if drift detected — acceptable here
