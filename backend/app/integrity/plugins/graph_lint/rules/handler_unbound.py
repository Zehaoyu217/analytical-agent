from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext

_HANDLER_PATH_PREFIXES = ("backend/app/api/", "backend/app/harness/")


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    routes_to_targets: set[str] = set()
    for link in ctx.graph.links:
        if link.get("relation") == "routes_to" and link.get("confidence") == "EXTRACTED":
            routes_to_targets.add(link["target"])

    issues: list[IntegrityIssue] = []
    for node in ctx.graph.nodes:
        if node.get("kind") != "function":
            continue
        src = node.get("source_file", "") or ""
        if not any(src.startswith(p) for p in _HANDLER_PATH_PREFIXES):
            continue
        label = node.get("label", "")
        if not label or label.startswith("_"):
            continue
        if node["id"] in routes_to_targets:
            continue
        issues.append(
            IntegrityIssue(
                rule="graph.handler_unbound",
                severity="WARN",
                node_id=node["id"],
                location=src,
                message=f"Handler {label!r} has no inbound routes_to edge",
                evidence={},
            )
        )
    return issues
