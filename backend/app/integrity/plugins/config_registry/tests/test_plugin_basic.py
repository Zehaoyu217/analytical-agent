"""Smoke test for ConfigRegistryPlugin orchestration."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.integrity.plugins.config_registry.plugin import ConfigRegistryPlugin
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot


def test_plugin_writes_manifest_and_artifact(tiny_repo: Path) -> None:
    plugin = ConfigRegistryPlugin(
        config={
            "manifest_path": "config/manifest.yaml",
            "skills_root": "backend/app/skills",
            "scripts_root": "scripts",
            "config_globs": [
                "pyproject.toml", "package.json", ".claude/settings.json",
                "vite.config.*", "tsconfig*.json", "Dockerfile*", "Makefile",
                ".env.example", "config/integrity.yaml",
            ],
            "excluded_paths": ["node_modules/**", "**/__pycache__/**"],
            "function_search_globs": [
                "backend/app/api/**/*.py", "backend/app/main.py",
            ],
            "function_decorators": ["router", "app", "api_router"],
            "function_event_handlers": ["startup", "shutdown", "lifespan"],
            "schema_drift": {"enabled": True, "strict_mode": False},
            "removed_escalation": {"enabled": True},
        },
        today=date(2026, 4, 17),
    )
    ctx = ScanContext(repo_root=tiny_repo, graph=GraphSnapshot.load(tiny_repo))
    result = plugin.scan(ctx)
    assert result.plugin_name == "config_registry"
    # Manifest written
    manifest_path = tiny_repo / "config/manifest.yaml"
    assert manifest_path.exists()
    body = manifest_path.read_text()
    assert "AUTO-GENERATED" in body
    # Artifact written
    artifact = tiny_repo / "integrity-out" / "2026-04-17" / "config_registry.json"
    assert artifact in result.artifacts
    payload = json.loads(artifact.read_text())
    assert "rules_run" in payload
    assert "issues" in payload


def test_plugin_handles_rule_exception_gracefully(tiny_repo: Path) -> None:
    """A buggy rule should yield ERROR issue, sibling rules continue."""
    def buggy(ctx, cfg, today):
        raise RuntimeError("boom")

    plugin = ConfigRegistryPlugin(
        config={"manifest_path": "config/manifest.yaml",
                "skills_root": "backend/app/skills",
                "scripts_root": "scripts",
                "config_globs": ["pyproject.toml"],
                "excluded_paths": [],
                "function_search_globs": [],
                "function_decorators": [],
                "function_event_handlers": [],
                "schema_drift": {"enabled": False},
                "removed_escalation": {"enabled": False}},
        today=date(2026, 4, 17),
        rules={"config.broken": buggy},
    )
    ctx = ScanContext(repo_root=tiny_repo, graph=GraphSnapshot.load(tiny_repo))
    result = plugin.scan(ctx)
    error_issues = [i for i in result.issues if i.severity == "ERROR"]
    assert error_issues
    assert any("config.broken" in f for f in result.failures)
