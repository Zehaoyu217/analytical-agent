from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....schema import GraphSnapshot
from ....snapshots import load_snapshot_by_age
from ..orphans import find_orphans


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    thresholds = config.get("thresholds", {})
    growth_pct = float(thresholds.get("orphan_growth_pct", 20))

    week = load_snapshot_by_age(ctx.repo_root, days=7, today=today)
    if week is None:
        return [
            IntegrityIssue(
                rule="graph.orphan_growth.no_baseline",
                severity="INFO",
                node_id="<no-baseline>",
                location="integrity-out/snapshots/",
                message="7-day-old snapshot missing — orphan_growth evaluation skipped.",
                evidence={},
            )
        ]

    today_count = len(find_orphans(ctx.graph))
    week_snap = GraphSnapshot(nodes=week.get("nodes", []), links=week.get("links", []))
    week_count = len(find_orphans(week_snap))

    if week_count == 0:
        return []

    growth_factor = 1.0 + (growth_pct / 100.0)
    if today_count <= growth_factor * week_count:
        return []

    pct = round((today_count / week_count - 1) * 100, 1)
    return [
        IntegrityIssue(
            rule="graph.orphan_growth",
            severity="WARN",
            node_id="<global>",
            location="<whole-graph>",
            message=f"Orphan count grew {pct}% week-over-week ({week_count} → {today_count})",
            evidence={"today": today_count, "week_ago": week_count, "growth_pct": pct},
        )
    ]
