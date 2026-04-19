from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ..index import MarkdownIndex
from ..parser.code_refs import extract_code_refs
from ..parser.git_log import GitLog


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def run(ctx: ScanContext, cfg: dict[str, Any], today: date) -> list[IntegrityIssue]:
    idx = MarkdownIndex.build(ctx.repo_root, cfg)
    stale_days = int(cfg.get("thresholds", {}).get("stale_days", 90))
    threshold = datetime.combine(today, datetime.min.time(), tzinfo=UTC) - timedelta(
        days=stale_days
    )
    gl = GitLog(ctx.repo_root)

    issues: list[IntegrityIssue] = []
    for rel in sorted(idx.docs):
        doc_iso = gl.last_commit_iso(rel)
        doc_dt = _parse_iso(doc_iso)
        if doc_dt is None:
            continue
        if doc_dt > threshold:
            continue

        parsed = idx.docs[rel]
        changed_refs: list[str] = []
        for ref in extract_code_refs(parsed.raw_text):
            if ref.kind not in ("path", "path_line") or not ref.path:
                continue
            src_iso = gl.last_commit_iso(ref.path)
            src_dt = _parse_iso(src_iso)
            if src_dt is None:
                continue
            if src_dt > doc_dt:
                changed_refs.append(ref.path)

        if not changed_refs:
            continue

        issues.append(
            IntegrityIssue(
                rule="doc.stale_candidate",
                severity="INFO",
                node_id=rel,
                location=rel,
                message=f"Doc {rel} unchanged >{stale_days}d while {len(changed_refs)} ref(s) moved",  # noqa: E501
                evidence={
                    "doc_last_commit": doc_iso,
                    "stale_days": stale_days,
                    "changed_refs": changed_refs,
                },
            )
        )
    return issues
