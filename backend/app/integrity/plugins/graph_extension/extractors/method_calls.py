from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from ....schema import GraphSnapshot
from ..schema import ExtractedEdge, ExtractionResult
from ._ast_helpers import node_id


def extract(repo_root: Path, graph: GraphSnapshot) -> ExtractionResult:
    """Resolve cross-file method calls (``obj.method()``) via a class registry.

    Two passes:

    1. **Class registry** — walk all backend Python files; record every
       ``ClassName.method`` definition with its file stem.
    2. **Call resolution** — for every ``obj.method()``, infer ``obj``'s
       class from local annotations / constructor assignments / function-arg
       hints, then emit ``caller → <file>_<class>_<method>``. If the type
       is unknown but the method name appears on exactly one class in the
       registry, emit to that class anyway (acceptable over-emit — same
       philosophy as ``cross_file_imports``' dual-emit).

    Skipped on purpose:
    - ``self.method()`` — already handled by ``intra_file_calls``.
    - Method calls on ``func().method()`` chains — would need return-type
      inference; out of scope for an import/call resolver.
    - Methods inherited from external base classes — the registry only
      knows what the codebase defines.
    """
    backend_root = repo_root / "backend"
    if not backend_root.exists():
        return ExtractionResult()

    failures: list[str] = []
    parsed: list[tuple[Path, ast.AST]] = []

    for path in sorted(backend_root.rglob("*.py")):
        if any(part.startswith(("__pycache__", ".")) for part in path.parts):
            continue
        try:
            parsed.append((path, ast.parse(path.read_text())))
        except SyntaxError as exc:
            failures.append(f"{path}: {exc}")

    method_owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path, tree in parsed:
        stem = path.stem.lower()
        for cls_node in _iter_classes(tree):
            for inner in cls_node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_owners[inner.name].append((stem, cls_node.name))

    edges: list[ExtractedEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()

    def add(src_id: str, tgt_id: str, rel: str, lineno: int) -> None:
        if not src_id or not tgt_id or src_id == tgt_id:
            return
        key = (src_id, tgt_id, "calls")
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append(
            ExtractedEdge(
                source=src_id,
                target=tgt_id,
                relation="calls",
                source_file=rel,
                source_location=lineno,
                extractor="method_calls",
            )
        )

    for path, tree in parsed:
        rel = str(path.relative_to(repo_root))
        stem = path.stem.lower()
        for caller_name, var_types, calls in _walk_funcs(tree):
            caller_id = node_id(stem, caller_name)
            for call in calls:
                if isinstance(call.func, ast.Name) and call.func.id and call.func.id[0].isupper():
                    cls = call.func.id
                    for owner_stem, owner_cls in method_owners.get("__init__", []):
                        if owner_cls == cls:
                            add(
                                caller_id,
                                _method_id(owner_stem, owner_cls, "__init__"),
                                rel,
                                call.lineno,
                            )
                            break
                    continue
                if not isinstance(call.func, ast.Attribute):
                    continue
                method = call.func.attr
                base = call.func.value
                if isinstance(base, ast.Name) and base.id == "self":
                    continue
                resolved: list[tuple[str, str]] = []
                if isinstance(base, ast.Name) and base.id in var_types:
                    cls = var_types[base.id]
                    for owner_stem, owner_cls in method_owners.get(method, []):
                        if owner_cls == cls:
                            resolved.append((owner_stem, owner_cls))
                            break
                if not resolved:
                    cands = method_owners.get(method, [])
                    if len(cands) == 1:
                        resolved.append(cands[0])
                for owner_stem, owner_cls in resolved:
                    add(caller_id, _method_id(owner_stem, owner_cls, method), rel, call.lineno)

    return ExtractionResult(edges=edges, failures=failures)


def _method_id(file_stem: str, class_name: str, method: str) -> str:
    """Graphify id for ClassName.method: ``<file>_<class>_<method.strip('_')>``."""
    return f"{file_stem.lower()}_{class_name.lower()}_{method.strip('_')}"


def _iter_classes(tree: ast.AST) -> Iterator[ast.ClassDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


def _walk_funcs(tree: ast.AST) -> Iterator[tuple[str, dict[str, str], list[ast.Call]]]:
    """Yield (func_name, {var: ClassName}, [Call, ...]) per top-level func and class method."""
    for top in ast.iter_child_nodes(tree):
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield top.name, _infer_types(top), _calls_in(top)
        elif isinstance(top, ast.ClassDef):
            for inner in top.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield inner.name, _infer_types(inner), _calls_in(inner)


def _calls_in(func: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(func) if isinstance(n, ast.Call)]


def _infer_types(func: ast.AST) -> dict[str, str]:
    """Best-effort var→ClassName from arg annotations, AnnAssign, and ``x = Cls(...)`` assigns."""
    types: dict[str, str] = {}
    if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for arg in list(func.args.args) + list(func.args.kwonlyargs):
            if arg.arg == "self":
                continue
            cls = _annotation_class(arg.annotation)
            if cls:
                types[arg.arg] = cls
    for node in ast.walk(func):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            cls = _annotation_class(node.annotation)
            if cls:
                types[node.target.id] = cls
        elif isinstance(node, ast.Assign):
            cls = _ctor_class(node.value)
            if cls:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        types[target.id] = cls
    return types


def _annotation_class(ann: ast.AST | None) -> str | None:
    """Pull a class name from an annotation: ``Foo``, ``Optional[Foo]``, ``list[Foo]`` → ``Foo``.

    Handles stringified PEP 563 annotations by parsing them.
    """
    if ann is None:
        return None
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        try:
            return _annotation_class(ast.parse(ann.value, mode="eval").body)
        except SyntaxError:
            return None
    if isinstance(ann, ast.Name):
        return ann.id
    if isinstance(ann, ast.Subscript):
        return _annotation_class(ann.slice)
    if isinstance(ann, ast.Attribute):
        return ann.attr
    return None


def _ctor_class(value: ast.AST | None) -> str | None:
    """If ``value`` is ``ClassName(...)`` or ``module.ClassName(...)``, return ``ClassName``.

    Heuristic: leading uppercase distinguishes a class from a function call.
    """
    if not isinstance(value, ast.Call):
        return None
    if isinstance(value.func, ast.Name):
        name = value.func.id
        return name if name and name[0].isupper() else None
    if isinstance(value.func, ast.Attribute):
        name = value.func.attr
        return name if name and name[0].isupper() else None
    return None
