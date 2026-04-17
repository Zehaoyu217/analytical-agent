"""``config.added`` — INFO when a manifest entry appears for the first time."""
from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ..manifest import diff_manifests


def run(
    ctx: ScanContext,
    cfg: dict[str, Any],
    today: date,
) -> list[IntegrityIssue]:
    current = cfg.get("_current_manifest") or {}
    prior = cfg.get("_prior_manifest") or {}
    delta = diff_manifests(current, prior)

    issues: list[IntegrityIssue] = []
    for key, entries in delta.added.items():
        for entry in entries:
            entry_id = str(entry.get("id"))
            issues.append(IntegrityIssue(
                rule="config.added",
                severity="INFO",
                node_id=entry_id,
                location=f"{key}:{entry_id}",
                message=f"New {key[:-1]} added to manifest: {entry_id}",
                evidence={"category": key, "entry": entry},
                fix_class=None,
            ))
    return issues
