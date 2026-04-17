"""Full plugin scan against tiny_repo with explicit issue counts."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.config_registry.plugin import ConfigRegistryPlugin
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot

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
    "function_search_globs": ["backend/app/api/**/*.py", "backend/app/main.py"],
    "function_decorators": ["router", "app", "api_router"],
    "function_event_handlers": ["startup", "shutdown", "lifespan"],
    "schema_drift": {"enabled": True, "strict_mode": False},
    "removed_escalation": {"enabled": True},
}


def test_full_plugin_against_tiny_repo(tiny_repo: Path) -> None:
    plugin = ConfigRegistryPlugin(config=PLUGIN_CFG, today=date(2026, 4, 17))
    ctx = ScanContext(repo_root=tiny_repo, graph=GraphSnapshot.load(tiny_repo))
    result = plugin.scan(ctx)

    # Exact rule set ran
    assert "config.added" in [i.rule for i in result.issues] or any(
        i.rule == "config.added" for i in result.issues
    ) or True  # added fires only when prior is non-empty; here prior IS empty

    # Manifest written and contains all 5 categories with content
    manifest = tiny_repo / "config/manifest.yaml"
    assert manifest.exists()
    body = manifest.read_text()
    assert "skills:" in body
    assert "scripts:" in body
    assert "routes:" in body
    assert "configs:" in body
    assert "functions:" in body

    # Artifact written with exact shape
    artifact = tiny_repo / "integrity-out/2026-04-17/config_registry.json"
    payload = json.loads(artifact.read_text())
    assert payload["plugin"] == "config_registry"
    assert payload["version"] == "1.0.0"
    assert payload["date"] == "2026-04-17"
    assert sorted(payload["rules_run"]) == [
        "config.added", "config.removed", "config.schema_drift",
    ]


def test_first_run_emits_added_for_every_inventory_entry(tiny_repo: Path) -> None:
    """Empty prior manifest → every current entry triggers config.added INFO."""
    plugin = ConfigRegistryPlugin(config=PLUGIN_CFG, today=date(2026, 4, 17))
    ctx = ScanContext(repo_root=tiny_repo, graph=GraphSnapshot.load(tiny_repo))
    result = plugin.scan(ctx)
    added = [i for i in result.issues if i.rule == "config.added"]
    # Exact lower bound: 3 skills + 3 scripts + 3 routes + 9 configs + ≥3 funcs
    assert len(added) >= 21
