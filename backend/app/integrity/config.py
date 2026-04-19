from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "plugins": {
        "graph_extension": {"enabled": True},
        "graph_lint": {
            "enabled": True,
            "thresholds": {
                "vulture_min_confidence": 80,
                "density_drop_pct": 25,
                "orphan_growth_pct": 20,
                "module_min_nodes": 5,
                "snapshot_retention_days": 30,
            },
            "ignored_dead_code": [],
            "excluded_paths": [
                "tests/**",
                "**/migrations/**",
                "**/__pycache__/**",
            ],
        },
        "doc_audit": {
            "enabled": True,
            "thresholds": {
                "stale_days": 90,
            },
            "coverage_required": [
                "dev-setup.md",
                "testing.md",
                "gotchas.md",
                "skill-creation.md",
                "log.md",
            ],
            "seed_docs": ["CLAUDE.md"],
            "doc_roots": [
                "docs/**/*.md",
                "knowledge/**/*.md",
                "*.md",
            ],
            "excluded_paths": [
                "reference/**",
                "node_modules/**",
                "**/__pycache__/**",
                "integrity-out/**",
                "docs/health/**",
                "docs/superpowers/**",
                "docs/log.md",
                "task_plan.md",
                "findings.md",
                "progress.md",
            ],
            "claude_ignore_file": ".claude-ignore",
            "rename_lookback": "30.days.ago",
            "disabled_rules": [],
        },
        "autofix": {
            "enabled": True,
            "apply": False,
            "fix_classes": {
                "claude_md_link": {"enabled": True},
                "doc_link_renamed": {"enabled": True},
                "manifest_regen": {"enabled": True},
                "dead_directive_cleanup": {"enabled": True},
                "health_dashboard_refresh": {"enabled": True},
            },
            "pr_concurrency_per_class": 1,
            "gh_executable": "gh",
            "branch_prefix": "integrity/autofix",
            "commit_author": "Integrity Autofix <integrity@local>",
            "dispatcher_subprocess_timeout_seconds": 60,
            "circuit_breaker": {
                "window_days": 30,
                "max_human_edits": 2,
            },
        },
    },
}

_INT_KEYS = {
    "vulture_min_confidence",
    "module_min_nodes",
    "snapshot_retention_days",
}
_FLOAT_KEYS = {
    "density_drop_pct",
    "orphan_growth_pct",
}


@dataclass(frozen=True)
class IntegrityConfig:
    plugins: dict[str, Any] = field(default_factory=dict)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coerce(key: str, raw: str) -> Any:
    if key in _INT_KEYS:
        return int(raw)
    if key in _FLOAT_KEYS:
        return float(raw)
    return raw


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = deepcopy(cfg)
    thresholds = cfg["plugins"]["graph_lint"]["thresholds"]
    for key in list(thresholds.keys()):
        env_var = f"INTEGRITY_{key.upper()}"
        if env_var in os.environ:
            thresholds[key] = _coerce(key, os.environ[env_var])
    return cfg


def load_config(repo_root: Path) -> IntegrityConfig:
    yaml_path = repo_root / "config" / "integrity.yaml"
    user: dict[str, Any] = {}
    if yaml_path.exists():
        loaded = yaml.safe_load(yaml_path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{yaml_path}: top-level must be a mapping")
        user = loaded
    merged = _deep_merge(DEFAULTS, user)
    merged = _apply_env_overrides(merged)
    return IntegrityConfig(plugins=merged["plugins"])
