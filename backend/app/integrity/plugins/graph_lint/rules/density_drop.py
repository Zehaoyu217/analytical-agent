from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....snapshots import load_snapshot_by_age


def _module_stats(nodes: list[dict], links: list[dict]) -> dict[str, tuple[int, int]]:
    """Return {source_file: (node_count, intra_module_edge_count)} for Python modules."""
    nodes_by_file: dict[str, set[str]] = defaultdict(set)
    for n in nodes:
        src = n.get("source_file", "") or ""
        if not src.endswith(".py"):
            continue
        nodes_by_file[src].add(n["id"])

    node_to_file: dict[str, str] = {}
    for src, ids in nodes_by_file.items():
        for nid in ids:
            node_to_file[nid] = src

    edges_per_file: dict[str, int] = defaultdict(int)
    for link in links:
        if link.get("confidence") != "EXTRACTED":
            continue
        sfile = node_to_file.get(link.get("source", ""))
        tfile = node_to_file.get(link.get("target", ""))
        if sfile is None or tfile is None or sfile != tfile:
            continue
        edges_per_file[sfile] += 1

    return {src: (len(ids), edges_per_file[src]) for src, ids in nodes_by_file.items()}


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    thresholds = config.get("thresholds", {})
    drop_pct = float(thresholds.get("density_drop_pct", 25))
    min_nodes = int(thresholds.get("module_min_nodes", 5))

    week = load_snapshot_by_age(ctx.repo_root, days=7, today=today)
    if week is None:
        return [
            IntegrityIssue(
                rule="graph.density_drop.no_baseline",
                severity="INFO",
                node_id="<no-baseline>",
                location="integrity-out/snapshots/",
                message="7-day-old snapshot missing — density_drop evaluation skipped.",
                evidence={},
            )
        ]

    today_stats = _module_stats(ctx.graph.nodes, ctx.graph.links)
    week_stats = _module_stats(week.get("nodes", []), week.get("links", []))

    threshold_factor = 1.0 - (drop_pct / 100.0)
    issues: list[IntegrityIssue] = []
    for src, (today_n, today_e) in today_stats.items():
        if today_n < min_nodes:
            continue
        if src not in week_stats:
            continue
        week_n, week_e = week_stats[src]
        if week_n < min_nodes:
            continue
        today_density = today_e / today_n
        week_density = week_e / week_n
        if week_density == 0:
            continue
        if today_density < threshold_factor * week_density:
            pct_drop = round((1 - today_density / week_density) * 100, 1)
            issues.append(
                IntegrityIssue(
                    rule="graph.density_drop",
                    severity="WARN",
                    node_id=src,
                    location=src,
                    message=f"Module density dropped {pct_drop}% week-over-week",
                    evidence={
                        "today_density": round(today_density, 3),
                        "week_density": round(week_density, 3),
                        "drop_pct": pct_drop,
                    },
                )
            )
    return issues
