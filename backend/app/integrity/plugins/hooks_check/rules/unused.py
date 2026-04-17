"""``hooks.unused`` — INFO when a hook is not justified by any coverage rule.

A hook is "justified" if its command contains the ``command_substring`` of
*some* coverage rule. The ``tolerated`` allowlist (substring) lets project
maintainers exempt formatters / utility hooks that everyone wants but no
explicit coverage rule asks for (e.g., ``sb inject``).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ..coverage import CoverageDoc
from ..settings_parser import HookRecord


def run(
    ctx: ScanContext,
    cfg: dict[str, Any],
    today: date,
) -> list[IntegrityIssue]:
    coverage: CoverageDoc = cfg["_coverage"]
    hooks: list[HookRecord] = cfg["_hooks"]
    rule_substrings = [r.requires_hook.command_substring for r in coverage.rules]
    tolerated = list(coverage.tolerated)

    issues: list[IntegrityIssue] = []
    for hook in hooks:
        if any(s and s in hook.command for s in rule_substrings):
            continue
        if any(t and t in hook.command for t in tolerated):
            continue
        idx = ":".join(str(i) for i in hook.source_index)
        issues.append(IntegrityIssue(
            rule="hooks.unused",
            severity="INFO",
            node_id=f"hook:{idx}",
            location=f".claude/settings.json#{idx}",
            message=(
                f"Hook is not justified by any coverage rule: "
                f"{hook.command[:80]!r}"
            ),
            evidence={
                "event": hook.event,
                "matcher": hook.matcher,
                "command": hook.command,
            },
            fix_class=None,
        ))
    return issues
