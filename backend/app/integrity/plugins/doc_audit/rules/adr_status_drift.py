from __future__ import annotations

import re
from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ..index import MarkdownIndex
from ..parser.code_refs import extract_code_refs


_BOLD_STATUS_RE = re.compile(
    r"^\s*\*\*Status:\*\*\s*Accepted\b", re.IGNORECASE | re.MULTILINE
)


def is_accepted(front_matter: dict[str, Any], raw_text: str) -> bool:
    fm_status = front_matter.get("status")
    if isinstance(fm_status, str) and fm_status.strip().lower() == "accepted":
        return True
    return bool(_BOLD_STATUS_RE.search(raw_text))


def _is_adr_doc(rel: str) -> bool:
    return rel.startswith("knowledge/adr/") and not rel.endswith("/template.md")


def _graph_indices(ctx: ScanContext) -> tuple[set[str], set[str]]:
    paths: set[str] = set()
    symbols: set[str] = set()
    for node in ctx.graph.nodes:
        sf = node.get("source_file")
        if isinstance(sf, str) and sf:
            paths.add(sf)
        nid = node.get("id")
        if isinstance(nid, str):
            symbols.add(nid.lower())
        label = node.get("label")
        if isinstance(label, str):
            symbols.add(label.lower())
    return paths, symbols


def run(ctx: ScanContext, cfg: dict[str, Any], today: date) -> list[IntegrityIssue]:
    idx = MarkdownIndex.build(ctx.repo_root, cfg)
    graph_paths, graph_symbols = _graph_indices(ctx)
    issues: list[IntegrityIssue] = []
    for rel in sorted(idx.docs):
        if not _is_adr_doc(rel):
            continue
        parsed = idx.docs[rel]
        if not is_accepted(parsed.front_matter, parsed.raw_text):
            continue
        for ref in extract_code_refs(parsed.raw_text):
            if ref.kind in ("path", "path_line") and ref.path:
                if ref.path in graph_paths:
                    continue
                if (ctx.repo_root / ref.path).exists():
                    continue
                issues.append(
                    IntegrityIssue(
                        rule="doc.adr_status_drift",
                        severity="WARN",
                        node_id=f"{rel}->{ref.path}",
                        location=f"{rel}:{ref.source_line}",
                        message=f"Accepted ADR references missing path: {ref.path}",
                        evidence={
                            "code_ref": ref.text,
                            "kind": ref.kind,
                            "source_line": ref.source_line,
                        },
                    )
                )
            elif ref.kind == "symbol" and ref.symbol and "." in ref.symbol:
                if ref.symbol.lower() in graph_symbols:
                    continue
                issues.append(
                    IntegrityIssue(
                        rule="doc.adr_status_drift",
                        severity="WARN",
                        node_id=f"{rel}->{ref.symbol}",
                        location=f"{rel}:{ref.source_line}",
                        message=f"Accepted ADR references missing symbol: {ref.symbol}",
                        evidence={
                            "code_ref": ref.text,
                            "kind": ref.kind,
                            "source_line": ref.source_line,
                        },
                    )
                )
    return issues
