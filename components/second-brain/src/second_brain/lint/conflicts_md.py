from __future__ import annotations

from datetime import UTC, datetime

from second_brain.config import Config
from second_brain.lint.runner import LintReport
from second_brain.lint.snapshot import load_snapshot


def render_conflicts_md(cfg: Config, report: LintReport) -> str:
    snap = load_snapshot(cfg)
    open_debates = [i for i in report.issues if i.rule == "UNRESOLVED_CONTRADICTION"]
    lopsided = [i for i in report.issues if i.rule == "LOPSIDED_CONTRADICTION"]

    resolved_pairs: list[str] = []
    for cid, claim in snap.claims.items():
        if claim.contradicts and claim.resolution:
            resolved_pairs.append(cid)

    lines: list[str] = []
    lines.append("# Conflicts")
    lines.append("")
    lines.append(f"_generated: {datetime.now(UTC).isoformat()}_")
    lines.append("")

    lines.append("## Open debates")
    lines.append("")
    if not open_debates:
        lines.append("_no open debates past grace period_")
    else:
        for issue in open_debates:
            targets = ", ".join(str(t) for t in issue.details.get("contradicts", []))
            lines.append(f"- **{issue.subject_id}** contradicts {targets}")
            lines.append(f"  > {issue.message}")
    lines.append("")

    lines.append("## Candidate contradictions")
    lines.append("")
    if not lopsided:
        lines.append("_no lopsided clusters flagged_")
    else:
        for issue in lopsided:
            attackers = issue.details.get("contradictors", [])
            lines.append(f"- **{issue.subject_id}** \u2190 {len(attackers)} contradictors")
            for a in attackers:
                lines.append(f"  - {a}")
    lines.append("")

    lines.append("## Healthy signal")
    lines.append("")
    lines.append(f"- resolved contradictions: {len(resolved_pairs)}")
    lines.append(f"- unresolved-past-grace: {len(open_debates)}")
    lines.append(f"- lopsided clusters: {len(lopsided)}")

    return "\n".join(lines) + "\n"


__all__ = ["render_conflicts_md"]
