"""Acceptance-gate proof: round-trip add fixture → scan → diff catches it."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.integrity.plugins.config_registry.plugin import ConfigRegistryPlugin
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot

PLUGIN_CFG = {
    "manifest_path": "config/manifest.yaml",
    "skills_root": "backend/app/skills",
    "scripts_root": "scripts",
    "config_globs": [
        "pyproject.toml", "package.json", ".claude/settings.json",
        "vite.config.*", "tsconfig*.json", "Dockerfile*", "Makefile",
        ".env.example", "config/integrity.yaml",
    ],
    "excluded_paths": ["node_modules/**", "**/__pycache__/**"],
    "function_search_globs": ["backend/app/api/**/*.py"],
    "function_decorators": ["router", "app"],
    "function_event_handlers": ["startup", "shutdown"],
    "schema_drift": {"enabled": False},
    "removed_escalation": {"enabled": True},
}


def _scan(repo: Path, today: date) -> list:
    plugin = ConfigRegistryPlugin(config=PLUGIN_CFG, today=today)
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))
    return plugin.scan(ctx).issues


def test_add_then_remove_round_trip(tiny_repo: Path) -> None:
    today = date(2026, 4, 17)

    # First scan — establishes baseline manifest at config/manifest.yaml.
    _scan(tiny_repo, today)

    # Add a brand-new script
    new_script = tiny_repo / "scripts" / "fixture_added.py"
    new_script.write_text("#!/usr/bin/env python3\nprint('hi')\n")

    issues = _scan(tiny_repo, today)
    added = [i for i in issues
             if i.rule == "config.added" and i.node_id == "scripts/fixture_added.py"]
    assert len(added) == 1, [i for i in issues if i.rule == "config.added"]

    # Remove it
    new_script.unlink()
    issues = _scan(tiny_repo, today)
    removed = [i for i in issues
               if i.rule == "config.removed"
               and i.node_id == "scripts/fixture_added.py"]
    assert len(removed) == 1
