"""Fixer: regenerate docs/health/latest.md and docs/health/trend.md.

Reads the day's aggregate report.json and the prior 30 days of report.json files
to render a trend table. Emits a Diff per file *only* if the regenerated content
differs from disk.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..diff import Diff, IssueRef
from ..loader import SiblingArtifacts

LATEST_REL = Path("docs/health/latest.md")
TREND_REL = Path("docs/health/trend.md")


def _normalize_plugins(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalize plugins field to {name: {issues, rules_run}} regardless of input shape.

    Production report.json uses a list: [{name, issue_count, failures, version}, ...].
    The fixer-internal fixture uses a dict: {name: {issues, rules_run}}.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", ""))
            if not name:
                continue
            out[name] = {
                "issues": int(entry.get("issue_count", entry.get("issues", 0)) or 0),
                "rules_run": list(entry.get("rules_run", [])),
            }
        return out
    return {}


def _render_latest(aggregate: dict[str, Any]) -> str:
    date_iso = str(aggregate.get("date", ""))
    by_sev = aggregate.get("by_severity") or aggregate.get("counts") or {}
    plugins = _normalize_plugins(aggregate.get("plugins"))
    issue_total = aggregate.get("issue_total")
    if issue_total is None:
        issues_raw = aggregate.get("issues")
        if isinstance(issues_raw, list):
            issue_total = len(issues_raw)
        else:
            issue_total = sum(int(p.get("issues", 0)) for p in plugins.values())
    lines = [
        f"# Integrity Health — {date_iso}",
        "",
        "## Summary",
        "",
        f"- Total issues: **{issue_total}**",
        f"- INFO: {by_sev.get('INFO', 0)}",
        f"- WARN: {by_sev.get('WARN', 0)}",
        f"- ERROR: {by_sev.get('ERROR', 0)}",
        f"- CRITICAL: {by_sev.get('CRITICAL', 0)}",
        "",
        "## Per-plugin",
        "",
        "| Plugin | Issues | Rules run |",
        "|--------|--------|-----------|",
    ]
    for name in sorted(plugins.keys()):
        p = plugins[name]
        rules = ", ".join(p.get("rules_run", [])) or "—"
        lines.append(f"| `{name}` | {p.get('issues', 0)} | {rules} |")
    lines.append("")
    return "\n".join(lines)


def _render_trend(repo_root: Path, today: date, window_days: int = 30) -> str:
    integrity_out = repo_root / "integrity-out"
    rows: list[tuple[str, int]] = []
    for offset in range(window_days):
        d = today - timedelta(days=offset)
        rpt = integrity_out / d.isoformat() / "report.json"
        if not rpt.exists():
            continue
        try:
            payload = json.loads(rpt.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        rows.append((d.isoformat(), int(payload.get("issue_total", 0))))
    rows.sort()
    lines = [
        f"# Integrity Trend — {today.isoformat()} (last {window_days} days)",
        "",
        "| Date | Issues |",
        "|------|--------|",
    ]
    for d_iso, total in rows:
        lines.append(f"| {d_iso} | {total} |")
    lines.append("")
    return "\n".join(lines)


def propose(
    artifacts: SiblingArtifacts,
    repo_root: Path,
    config: dict[str, Any],
) -> list[Diff]:
    if not artifacts.aggregate:
        return []

    aggregate = artifacts.aggregate
    today_iso = str(aggregate.get("date", ""))
    try:
        today = (
            datetime.strptime(today_iso, "%Y-%m-%d").date()
            if today_iso
            else date.today()
        )
    except ValueError:
        today = date.today()

    refs = (IssueRef(
        plugin="aggregate",
        rule="aggregate.snapshot",
        message=f"refresh dashboard for {today_iso}",
        evidence={"date": today_iso},
    ),)

    out: list[Diff] = []

    latest_path = repo_root / LATEST_REL
    latest_orig = latest_path.read_text() if latest_path.exists() else ""
    latest_new = _render_latest(aggregate)
    if latest_new != latest_orig:
        out.append(Diff(
            path=LATEST_REL,
            original_content=latest_orig,
            new_content=latest_new,
            rationale="Refresh docs/health/latest.md from today's report",
            source_issues=refs,
        ))

    trend_path = repo_root / TREND_REL
    trend_orig = trend_path.read_text() if trend_path.exists() else ""
    trend_new = _render_trend(repo_root, today)
    if trend_new != trend_orig:
        out.append(Diff(
            path=TREND_REL,
            original_content=trend_orig,
            new_content=trend_new,
            rationale="Refresh docs/health/trend.md (rolling 30-day window)",
            source_issues=refs,
        ))

    return out
