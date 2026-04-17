"""Fixer: regenerate config/manifest.yaml when Plugin E reports drift.

Delegates to Plugin E's `emit_manifest_text` to produce the regenerated
YAML without writing to disk. Skips when the regenerated content is
byte-identical to the on-disk manifest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..diff import Diff, IssueRef
from ..loader import SiblingArtifacts

DRIFT_RULES = {"config.added", "config.removed", "config.check_drift"}
MANIFEST_REL = Path("config/manifest.yaml")


def _regenerate_manifest_text(repo_root: Path) -> str:
    from backend.app.integrity.plugins.config_registry.manifest import (
        emit_manifest_text,
    )
    return emit_manifest_text(repo_root)


def propose(
    artifacts: SiblingArtifacts,
    repo_root: Path,
    config: dict[str, Any],
) -> list[Diff]:
    if not artifacts.config_registry:
        return []

    drift_issues = [
        i for i in artifacts.config_registry.get("issues", [])
        if i.get("rule") in DRIFT_RULES
    ]
    if not drift_issues:
        return []

    manifest_path = repo_root / MANIFEST_REL
    original = manifest_path.read_text() if manifest_path.exists() else ""
    new_content = _regenerate_manifest_text(repo_root)

    if new_content == original:
        return []

    refs = tuple(
        IssueRef(
            plugin="config_registry",
            rule=str(i.get("rule", "")),
            message=str(i.get("message", "")),
            evidence=dict(i.get("evidence", {})),
        )
        for i in drift_issues
    )
    rationale = (
        f"Regenerate config/manifest.yaml ({len(drift_issues)} drift signal(s))"
    )
    return [Diff(
        path=MANIFEST_REL,
        original_content=original,
        new_content=new_content,
        rationale=rationale,
        source_issues=refs,
    )]
