from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from second_brain.config import Config
from second_brain.lint.rules import (
    LintIssue,
    Severity,
    check_circular_supersedes,
    check_dangling_edge,
    check_hash_mismatch,
    check_lopsided_contradiction,
    check_orphan_claim,
    check_sparse_source,
    check_stale_abstract,
    check_unresolved_contradiction,
)
from second_brain.lint.snapshot import KBSnapshot, load_snapshot


@dataclass(frozen=True)
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def counts_by_severity(self) -> dict[str, int]:
        out = {"error": 0, "warning": 0, "info": 0}
        for i in self.issues:
            out[i.severity.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "counts_by_severity": self.counts_by_severity,
            "issues": [
                {
                    "rule": i.rule,
                    "severity": i.severity.value,
                    "subject_id": i.subject_id,
                    "message": i.message,
                    "details": dict(i.details),
                }
                for i in self.issues
            ],
        }


SnapshotRule = Callable[[KBSnapshot], list[LintIssue]]
SnapshotCfgRule = Callable[[KBSnapshot, Config], list[LintIssue]]

_SNAPSHOT_RULES: list[SnapshotRule] = [
    check_orphan_claim,
    check_dangling_edge,
    check_circular_supersedes,
    check_sparse_source,
    check_unresolved_contradiction,
    check_lopsided_contradiction,
]

_SNAPSHOT_CFG_RULES: list[SnapshotCfgRule] = [
    check_hash_mismatch,
    check_stale_abstract,
]


def run_lint(cfg: Config) -> LintReport:
    snap = load_snapshot(cfg)
    issues: list[LintIssue] = []
    for rule in _SNAPSHOT_RULES:
        issues.extend(rule(snap))
    for rule_cfg in _SNAPSHOT_CFG_RULES:
        issues.extend(rule_cfg(snap, cfg))
    issues.sort(key=lambda i: (i.severity.value, i.rule, i.subject_id))
    return LintReport(issues=issues)
