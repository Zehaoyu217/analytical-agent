from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from second_brain.config import Config
from second_brain.lint.snapshot import KBSnapshot


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class LintIssue:
    rule: str
    severity: Severity
    subject_id: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash((self.rule, self.severity, self.subject_id, self.message))


DEFAULT_GRACE_DAYS: int = 14
LOPSIDED_THRESHOLD: int = 3


def check_orphan_claim(snap: KBSnapshot) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for cid, claim in snap.claims.items():
        if claim.status != "active":
            continue
        live_supports = [s for s in claim.supports if _id_of(s) in snap.sources]
        if not live_supports:
            issues.append(LintIssue(
                rule="ORPHAN_CLAIM",
                severity=Severity.ERROR,
                subject_id=cid,
                message=f"claim {cid!r} has no live supports target",
            ))
    return issues


def check_dangling_edge(snap: KBSnapshot) -> list[LintIssue]:
    known = snap.all_ids
    issues: list[LintIssue] = []
    for sid, src in snap.sources.items():
        for attr in ("cites", "related", "supersedes"):
            for tgt in getattr(src, attr):
                tid = _id_of(tgt)
                if tid not in known:
                    issues.append(LintIssue(
                        rule="DANGLING_EDGE",
                        severity=Severity.ERROR,
                        subject_id=sid,
                        message=f"{sid} {attr} → unknown id {tid!r}",
                        details={"relation": attr, "target": tgt},
                    ))
    for cid, claim in snap.claims.items():
        for attr in ("supports", "contradicts", "refines"):
            for tgt in getattr(claim, attr):
                tid = _id_of(tgt)
                if tid not in known:
                    issues.append(LintIssue(
                        rule="DANGLING_EDGE",
                        severity=Severity.ERROR,
                        subject_id=cid,
                        message=f"{cid} {attr} → unknown id {tid!r}",
                        details={"relation": attr, "target": tgt},
                    ))
    return issues


def check_circular_supersedes(snap: KBSnapshot) -> list[LintIssue]:
    graph: dict[str, list[str]] = {
        sid: [_id_of(t) for t in src.supersedes]
        for sid, src in snap.sources.items()
    }
    cycles = _find_cycles(graph)
    issues: list[LintIssue] = []
    for cycle in cycles:
        rep = min(cycle)
        issues.append(LintIssue(
            rule="CIRCULAR_SUPERSEDES",
            severity=Severity.ERROR,
            subject_id=rep,
            message=f"supersedes cycle: {' → '.join(cycle)} → {cycle[0]}",
            details={"cycle": cycle},
        ))
    return issues


def check_hash_mismatch(snap: KBSnapshot, cfg: Config) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for sid, src in snap.sources.items():
        folder = cfg.sources_dir / sid
        for raw in src.raw:
            p = folder / raw.path
            if not p.exists():
                continue
            digest = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
            if digest != raw.sha256:
                issues.append(LintIssue(
                    rule="HASH_MISMATCH",
                    severity=Severity.ERROR,
                    subject_id=sid,
                    message=f"raw artifact {raw.path!r} hash changed",
                    details={"path": raw.path, "stored": raw.sha256, "current": digest},
                ))
                continue  # one issue per artifact is enough
        # The top-level content_hash should match at least one raw artifact's hash,
        # or if only one artifact exists, it must match that artifact.
        if src.content_hash and src.raw:
            any_match = any(src.content_hash == r.sha256 for r in src.raw)
            if not any_match:
                issues.append(LintIssue(
                    rule="HASH_MISMATCH",
                    severity=Severity.ERROR,
                    subject_id=sid,
                    message="content_hash does not match any raw artifact",
                    details={"content_hash": src.content_hash,
                             "raw_hashes": [r.sha256 for r in src.raw]},
                ))
    return issues


def check_stale_abstract(snap: KBSnapshot, cfg: Config) -> list[LintIssue]:
    mismatches = {i.subject_id for i in check_hash_mismatch(snap, cfg)}
    issues: list[LintIssue] = []
    for sid in mismatches:
        src = snap.sources.get(sid)
        if src and src.abstract.strip():
            issues.append(LintIssue(
                rule="STALE_ABSTRACT",
                severity=Severity.WARNING,
                subject_id=sid,
                message=f"abstract may be stale: content_hash drift on {sid}",
            ))
    return issues


def check_sparse_source(snap: KBSnapshot) -> list[LintIssue]:
    sourced: set[str] = set()
    for claim in snap.claims.values():
        for tgt in claim.supports:
            sourced.add(_id_of(tgt))
    issues: list[LintIssue] = []
    for sid, src in snap.sources.items():
        if src.kind == "failed":
            continue
        if sid not in sourced:
            issues.append(LintIssue(
                rule="SPARSE_SOURCE",
                severity=Severity.WARNING,
                subject_id=sid,
                message=f"source {sid} has 0 claims grounded in it",
            ))
    return issues


def check_unresolved_contradiction(
    snap: KBSnapshot, *, grace_days: int = DEFAULT_GRACE_DAYS
) -> list[LintIssue]:
    cutoff = datetime.now(UTC) - timedelta(days=grace_days)
    issues: list[LintIssue] = []
    for cid, claim in snap.claims.items():
        if not claim.contradicts:
            continue
        if claim.resolution:
            continue
        if claim.extracted_at and _ensure_aware(claim.extracted_at) > cutoff:
            continue
        issues.append(LintIssue(
            rule="UNRESOLVED_CONTRADICTION",
            severity=Severity.WARNING,
            subject_id=cid,
            message=f"contradiction on {cid} unresolved past grace period",
            details={"contradicts": list(claim.contradicts), "grace_days": grace_days},
        ))
    return issues


def check_lopsided_contradiction(
    snap: KBSnapshot, *, threshold: int = LOPSIDED_THRESHOLD
) -> list[LintIssue]:
    inbound: dict[str, list[str]] = {cid: [] for cid in snap.claims}
    for src_cid, claim in snap.claims.items():
        for tgt in claim.contradicts:
            tid = _id_of(tgt)
            if tid in inbound:
                inbound[tid].append(src_cid)
    issues: list[LintIssue] = []
    for cid, attackers in inbound.items():
        if len(attackers) < threshold:
            continue
        outbound = snap.claims[cid].contradicts
        if outbound:
            continue
        issues.append(LintIssue(
            rule="LOPSIDED_CONTRADICTION",
            severity=Severity.WARNING,
            subject_id=cid,
            message=f"{cid} is contradicted by {len(attackers)} claims but contradicts none",
            details={"contradictors": attackers, "threshold": threshold},
        ))
    return issues


def _id_of(edge_target: str) -> str:
    return edge_target.split("#", 1)[0]


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    visited: set[str] = set()
    on_stack: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        if node in on_stack:
            idx = stack.index(node)
            cycles.append(stack[idx:])
            return
        if node in visited:
            return
        visited.add(node)
        on_stack.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            dfs(nxt)
        on_stack.discard(node)
        stack.pop()

    for n in graph:
        dfs(n)
    # Deduplicate cycles by frozenset of members.
    seen: set[frozenset[str]] = set()
    deduped: list[list[str]] = []
    for c in cycles:
        key = frozenset(c)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


__all__ = [
    "DEFAULT_GRACE_DAYS",
    "LOPSIDED_THRESHOLD",
    "LintIssue",
    "Severity",
    "check_circular_supersedes",
    "check_dangling_edge",
    "check_hash_mismatch",
    "check_lopsided_contradiction",
    "check_orphan_claim",
    "check_sparse_source",
    "check_stale_abstract",
    "check_unresolved_contradiction",
]
