from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ...graph_lint.git_renames import recent_renames
from ..index import MarkdownIndex


_ABSOLUTE_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "tel:")


def _resolve_target(base_dir: PurePosixPath, target: str) -> str | None:
    parts: list[str] = []
    for part in (base_dir / target).parts:
        if part == "..":
            if parts:
                parts.pop()
            else:
                return None
        elif part == ".":
            continue
        else:
            parts.append(part)
    return PurePosixPath(*parts).as_posix() if parts else None


def run(ctx: ScanContext, cfg: dict[str, Any], today: date) -> list[IntegrityIssue]:
    idx = MarkdownIndex.build(ctx.repo_root, cfg)
    rename_lookback = cfg.get("rename_lookback", "30.days.ago")
    renames = recent_renames(ctx.repo_root, since=rename_lookback)

    issues: list[IntegrityIssue] = []
    for rel in sorted(idx.docs):
        parsed = idx.docs[rel]
        base_dir = PurePosixPath(rel).parent
        for link in parsed.links:
            target_lower = (link.target or "").lower()
            if target_lower.startswith(_ABSOLUTE_PREFIXES):
                continue

            # In-page anchor: target empty, anchor present -> validate against this doc's anchors
            if not link.target and link.anchor:
                if link.anchor not in idx.anchors_by_path.get(rel, set()):
                    issues.append(
                        IntegrityIssue(
                            rule="doc.broken_link",
                            severity="WARN",
                            node_id=f"{rel}#{link.anchor}",
                            location=f"{rel}:{link.line}",
                            message=f"Anchor #{link.anchor} not found in {rel}",
                            evidence={
                                "target": rel,
                                "anchor": link.anchor,
                                "in_page": True,
                            },
                            fix_class=None,
                        )
                    )
                continue

            if not link.target:
                continue
            # Skip non-markdown intra-repo links (images, code files, etc.) -- out of scope
            if not link.target.endswith(".md"):
                continue

            resolved = _resolve_target(base_dir, link.target)
            if resolved is None:
                continue

            target_path = ctx.repo_root / resolved
            if not target_path.is_file():
                fix_class = None
                evidence: dict[str, Any] = {"target": resolved}
                if resolved in renames:
                    fix_class = "doc_link_renamed"
                    evidence["rename_to"] = renames[resolved]
                issues.append(
                    IntegrityIssue(
                        rule="doc.broken_link",
                        severity="WARN",
                        node_id=f"{rel}->{resolved}",
                        location=f"{rel}:{link.line}",
                        message=f"Broken link: {resolved}",
                        evidence=evidence,
                        fix_class=fix_class,
                    )
                )
                continue

            if link.anchor:
                if link.anchor not in idx.anchors_by_path.get(resolved, set()):
                    issues.append(
                        IntegrityIssue(
                            rule="doc.broken_link",
                            severity="WARN",
                            node_id=f"{rel}->{resolved}#{link.anchor}",
                            location=f"{rel}:{link.line}",
                            message=f"Anchor #{link.anchor} not found in {resolved}",
                            evidence={
                                "target": resolved,
                                "anchor": link.anchor,
                            },
                            fix_class=None,
                        )
                    )
    return issues
