from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from ....schema import GraphSnapshot
from ..schema import ExtractedEdge, ExtractionResult
from ._ast_helpers import node_id


def extract(repo_root: Path, graph: GraphSnapshot) -> ExtractionResult:
    failures: list[str] = []
    edges: list[ExtractedEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()

    backend_root = repo_root / "backend" / "app"
    if not backend_root.exists():
        return ExtractionResult()

    for path in sorted(backend_root.rglob("*.py")):
        if any(part.startswith(("__pycache__", ".")) for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            failures.append(f"{path}: {exc}")
            continue

        rel = str(path.relative_to(repo_root))
        stem = path.stem
        local_defs = _collect_local_defs(tree)
        for caller_name, call_node, _ in _iter_calls_with_caller(tree):
            target = _resolve_callee(call_node, local_defs)
            if target is None:
                continue
            src_id = node_id(stem, caller_name)
            tgt_id = node_id(stem, target)
            edge_key = (src_id, tgt_id, "calls")
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append(
                ExtractedEdge(
                    source=src_id,
                    target=tgt_id,
                    relation="calls",
                    source_file=rel,
                    source_location=call_node.lineno,
                    extractor="intra_file_calls",
                )
            )

    return ExtractionResult(edges=edges, failures=failures)


def _collect_local_defs(tree: ast.AST) -> set[str]:
    """Module-level def/async def/class names + class-method names."""
    out: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        if isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(inner.name)
    return out


def _iter_calls_with_caller(tree: ast.AST) -> Iterator[tuple[str, ast.Call, str | None]]:
    """Yield (caller_name, Call node, parent_class_or_None) for every Call."""
    for top in ast.iter_child_nodes(tree):
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(top):
                if isinstance(child, ast.Call):
                    yield top.name, child, None
        elif isinstance(top, ast.ClassDef):
            for inner in top.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(inner):
                        if isinstance(child, ast.Call):
                            yield inner.name, child, top.name


def _resolve_callee(call: ast.Call, local_defs: set[str]) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id if func.id in local_defs else None
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "self"
    ):
        return func.attr if func.attr in local_defs else None
    return None
