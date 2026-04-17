"""``config.removed`` — INFO normally; WARN when id still referenced in graph."""
from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....schema import GraphSnapshot
from ..manifest import diff_manifests


def build_dep_index(graph: GraphSnapshot) -> set[str]:
    """Flatten every node id and source_file value into one lookup set."""
    index: set[str] = set()
    for node in graph.nodes:
        nid = str(node.get("id", ""))
        if nid:
            index.add(nid)
        sf = node.get("source_file")
        if isinstance(sf, str) and sf:
            index.add(sf)
    return index


def run(
    ctx: ScanContext,
    cfg: dict[str, Any],
    today: date,
) -> list[IntegrityIssue]:
    current = cfg.get("_current_manifest") or {}
    prior = cfg.get("_prior_manifest") or {}
    dep_index: set[str] = cfg.get("_dep_graph") or build_dep_index(ctx.graph)
    escalation_enabled = bool(
        cfg.get("removed_escalation", {}).get("enabled", True)
    )

    delta = diff_manifests(current, prior)
    issues: list[IntegrityIssue] = []
    for key, entries in delta.removed.items():
        for entry in entries:
            entry_id = str(entry.get("id"))
            referenced = escalation_enabled and entry_id in dep_index
            severity = "WARN" if referenced else "INFO"
            msg_suffix = (
                " (still referenced in dep graph)" if referenced else ""
            )
            issues.append(IntegrityIssue(
                rule="config.removed",
                severity=severity,
                node_id=entry_id,
                location=f"{key}:{entry_id}",
                message=f"Removed from manifest: {entry_id}{msg_suffix}",
                evidence={
                    "category": key,
                    "entry": entry,
                    "still_referenced": referenced,
                },
                fix_class=None,
            ))
    return issues
