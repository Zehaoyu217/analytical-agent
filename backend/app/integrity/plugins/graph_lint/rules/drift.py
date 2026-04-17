from __future__ import annotations

import fnmatch
from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....snapshots import load_snapshot_by_age
from ..git_renames import recent_renames


def _matches_any_glob(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _node_index(snap_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in snap_payload.get("nodes", [])}


def _no_baseline_issue() -> IntegrityIssue:
    return IntegrityIssue(
        rule="graph.drift.no_baseline",
        severity="INFO",
        node_id="<no-baseline>",
        location="integrity-out/snapshots/",
        message="Yesterday's snapshot missing — drift evaluation skipped (first runs only).",
        evidence={},
    )


def run_added(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    yesterday = load_snapshot_by_age(ctx.repo_root, days=1, today=today)
    if yesterday is None:
        return [_no_baseline_issue()]
    excluded = list(config.get("excluded_paths", []))
    yest_index = _node_index(yesterday)
    issues: list[IntegrityIssue] = []
    for node in ctx.graph.nodes:
        nid = node["id"]
        if nid in yest_index:
            continue
        src = node.get("source_file", "") or ""
        if _matches_any_glob(src, excluded):
            continue
        issues.append(
            IntegrityIssue(
                rule="graph.drift_added",
                severity="INFO",
                node_id=nid,
                location=src or "<unknown>",
                message=f"Node {nid!r} added since yesterday",
                evidence={},
            )
        )
    return issues


def run_removed(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    yesterday = load_snapshot_by_age(ctx.repo_root, days=1, today=today)
    if yesterday is None:
        return [_no_baseline_issue()]
    excluded = list(config.get("excluded_paths", []))
    today_ids = {n["id"] for n in ctx.graph.nodes}
    renames = recent_renames(ctx.repo_root, since="1.day.ago")
    issues: list[IntegrityIssue] = []
    for node in yesterday.get("nodes", []):
        nid = node["id"]
        if nid in today_ids:
            continue
        src = node.get("source_file", "") or ""
        if _matches_any_glob(src, excluded):
            continue
        was_renamed = src in renames
        severity = "INFO" if was_renamed else "WARN"
        msg_suffix = f" (file renamed → {renames[src]})" if was_renamed else ""
        issues.append(
            IntegrityIssue(
                rule="graph.drift_removed",
                severity=severity,
                node_id=nid,
                location=src or "<unknown>",
                message=f"Node {nid!r} removed since yesterday{msg_suffix}",
                evidence={"renamed_to": renames.get(src)} if was_renamed else {},
            )
        )
    return issues
