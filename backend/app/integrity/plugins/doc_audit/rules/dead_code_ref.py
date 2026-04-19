from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ..index import MarkdownIndex
from ..parser.code_refs import extract_code_refs


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


def _is_adr(rel: str) -> bool:
    return rel.startswith("knowledge/adr/")


# Symbols whose roots are stdlib/third-party — never project-owned, so a
# missing graph entry is meaningless. The match is on the leading dotted
# component (case-insensitive).
_STDLIB_ROOTS = frozenset({
    "os", "sys", "io", "json", "re", "math", "time", "datetime", "pathlib",
    "subprocess", "shutil", "tempfile", "logging", "typing", "collections",
    "functools", "itertools", "contextlib", "asyncio", "threading", "uuid",
    "hashlib", "base64", "random", "warnings", "dataclasses", "enum",
    "abc", "inspect", "ast", "argparse", "concurrent", "queue", "sqlite3",
    # very common third-party namespaces in this repo
    "np", "pd", "plt", "alt", "duckdb", "fastapi", "pydantic", "ruamel",
    "scipy", "sklearn", "altair", "pandas", "numpy", "matplotlib",
    "requests", "httpx", "anyio", "starlette",
    # integrity plugin rule-name roots (e.g. `doc.dead_code_ref`,
    # `hooks.missing`, `config.added`, `graph.density_drop`,
    # `autofix.fixer_failed`) — these are rule identifiers surfaced in
    # docs/changelog, not Python symbols.
    "doc", "hooks", "config", "graph", "autofix", "skill",
})


def _is_external_symbol(symbol: str) -> bool:
    root = symbol.split(".", 1)[0].lower()
    return root in _STDLIB_ROOTS


_PATH_PREFIXES: tuple[str, ...] = (
    "backend/",
    "backend/app/",
    "frontend/src/",
    "frontend/",
    "reference/src/",
    "reference/",
)


def _path_resolves(ctx: ScanContext, target: str, graph_paths: set[str]) -> bool:
    if target in graph_paths:
        return True
    if (ctx.repo_root / target).exists():
        return True
    # Docs commonly reference paths without the project prefix
    # (e.g. `harness/loop.py`, `app/main.py`, `components/Button.tsx`).
    # Try a few well-known roots before giving up.
    if not target.startswith(("backend/", "frontend/", "infra/", "reference/")):
        for prefix in _PATH_PREFIXES:
            if (ctx.repo_root / prefix / target).exists():
                return True
    return False


def run(ctx: ScanContext, cfg: dict[str, Any], today: date) -> list[IntegrityIssue]:
    idx = MarkdownIndex.build(ctx.repo_root, cfg)
    graph_paths, graph_symbols = _graph_indices(ctx)
    issues: list[IntegrityIssue] = []
    for rel in sorted(idx.docs):
        if _is_adr(rel):
            continue  # handled by adr_status_drift
        parsed = idx.docs[rel]
        refs = extract_code_refs(parsed.raw_text)
        for ref in refs:
            if ref.kind in ("path", "path_line"):
                target = ref.path or ""
                if not target:
                    continue
                if _path_resolves(ctx, target, graph_paths):
                    continue
                issues.append(
                    IntegrityIssue(
                        rule="doc.dead_code_ref",
                        severity="WARN",
                        node_id=f"{rel}->{target}",
                        location=f"{rel}:{ref.source_line}",
                        message=f"Dead code reference: {target}",
                        evidence={
                            "code_ref": ref.text,
                            "kind": ref.kind,
                            "source_line": ref.source_line,
                        },
                    )
                )
            elif ref.kind == "symbol":
                if not ref.symbol or "." not in ref.symbol:
                    continue
                if _is_external_symbol(ref.symbol):
                    continue
                if ref.symbol.lower() in graph_symbols:
                    continue
                issues.append(
                    IntegrityIssue(
                        rule="doc.dead_code_ref",
                        severity="WARN",
                        node_id=f"{rel}->{ref.symbol}",
                        location=f"{rel}:{ref.source_line}",
                        message=f"Dead symbol reference: {ref.symbol}",
                        evidence={
                            "code_ref": ref.text,
                            "kind": ref.kind,
                            "source_line": ref.source_line,
                        },
                    )
                )
    return issues
