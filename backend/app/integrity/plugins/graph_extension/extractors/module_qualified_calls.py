from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from ....schema import GraphSnapshot
from ..schema import ExtractedEdge, ExtractionResult
from ._ast_helpers import node_id


def extract(repo_root: Path, graph: GraphSnapshot) -> ExtractionResult:
    """Resolve ``mod.fn()`` calls where ``mod`` is an imported *module* (not a class).

    Three passes:

    1. **Module index** — every ``backend/**/*.py`` indexed by its absolute
       dotted path (``app.trace.bus`` for ``backend/app/trace/bus.py``;
       ``app.trace`` for ``backend/app/trace/__init__.py``).
    2. **Function registry** — top-level ``def``/``async def`` names per module.
    3. **Call resolution** — for each function, build local module bindings
       from module-level ``import``/``from … import …`` statements (filtered to
       names that map to real ``.py`` files), then walk every ``Call``. If the
       call shape is ``X.fn()`` and ``X`` resolves to a known module ``M`` that
       defines top-level ``fn``, emit ``caller → <M_stem>_<fn>`` (relation
       ``calls``).

    Skipped on purpose:
    - Symbol imports (``from x import Foo`` where ``Foo`` is a class) — handled
      by ``method_calls`` and ``cross_file_imports``.
    - Attribute access on shadowed locals (``bus = build()`` then ``bus.x()``).
    - Calls on chains we cannot reduce to a dotted module path.
    - Method calls on instance attributes (``self.bus.publish()``).
    """
    backend_root = repo_root / "backend"
    if not backend_root.exists():
        return ExtractionResult()

    failures: list[str] = []
    parsed: list[tuple[Path, tuple[str, ...], ast.AST]] = []

    for path in sorted(backend_root.rglob("*.py")):
        if any(part.startswith(("__pycache__", ".")) for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            failures.append(f"{path}: {exc}")
            continue
        rel = path.relative_to(backend_root)
        file_pkg = tuple(rel.parts[:-1])
        parsed.append((path, file_pkg, tree))

    module_index: dict[str, Path] = {}
    for path, file_pkg, _ in parsed:
        if path.name == "__init__.py":
            dotted = ".".join(p.lower() for p in file_pkg)
            if dotted:
                module_index[dotted] = path
        else:
            parts = list(file_pkg) + [path.stem]
            module_index[".".join(p.lower() for p in parts)] = path

    module_functions: dict[str, set[str]] = {}
    for dotted, path in module_index.items():
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        module_functions[dotted] = {
            n.name
            for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    edges: list[ExtractedEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()

    def add(src_id: str, tgt_id: str, rel_path: str, lineno: int) -> None:
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
                source_file=rel_path,
                source_location=lineno,
                extractor="module_qualified_calls",
            )
        )

    for src_path, src_pkg, src_tree in parsed:
        rel_str = str(src_path.relative_to(repo_root))
        src_stem = src_path.stem.lower()
        bindings = _module_bindings(src_tree, src_pkg, module_index)
        for caller_name, func_node in _iter_callers(src_tree):
            caller_id = node_id(src_stem, caller_name)
            shadows = _local_shadows(func_node)
            for call in (n for n in ast.walk(func_node) if isinstance(n, ast.Call)):
                if not isinstance(call.func, ast.Attribute):
                    continue
                chain = _attr_chain(call.func.value)
                if not chain or chain[0] in shadows:
                    continue
                fn = call.func.attr
                mod = _resolve_chain(chain, bindings, module_index)
                if mod is None or fn not in module_functions.get(mod, set()):
                    continue
                target_stem = module_index[mod].stem.lower()
                add(caller_id, node_id(target_stem, fn), rel_str, call.lineno)

    return ExtractionResult(edges=edges, failures=failures)


def _attr_chain(node: ast.AST) -> list[str] | None:
    """Reduce ``a.b.c`` to ``['a', 'b', 'c']``; return None if any non-attr/Name link."""
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    parts.reverse()
    return parts


def _resolve_chain(
    chain: list[str], bindings: dict[str, str], module_index: dict[str, Path]
) -> str | None:
    """Map an attr chain to a module path in the index, via bindings or direct lookup."""
    if not chain:
        return None
    head = chain[0]
    if head in bindings:
        base = bindings[head]
        if len(chain) == 1:
            return base if base in module_index else None
        candidate = base + "." + ".".join(p.lower() for p in chain[1:])
        return candidate if candidate in module_index else None
    dotted = ".".join(p.lower() for p in chain)
    return dotted if dotted in module_index else None


def _module_bindings(
    tree: ast.AST, file_pkg: tuple[str, ...], module_index: dict[str, Path]
) -> dict[str, str]:
    """Map each module-level local name → absolute dotted module path.

    Only includes bindings that resolve to a real module in ``module_index``.
    """
    bindings: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            base = _resolve_relative(node.level, node.module, file_pkg)
            if node.level > 0 and base is None:
                continue
            for alias in node.names:
                name = alias.name
                if name == "*" or not name:
                    continue
                local = alias.asname or name
                candidate = (f"{base}.{name}".lower()) if base else name.lower()
                if candidate in module_index:
                    bindings[local] = candidate
        elif isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name.lower()
                if alias.asname:
                    if full in module_index:
                        bindings[alias.asname] = full
                else:
                    if "." not in full and full in module_index:
                        bindings[alias.name] = full
    return bindings


def _resolve_relative(
    level: int, module: str | None, file_pkg: tuple[str, ...]
) -> str | None:
    """Resolve a (level, module) ImportFrom to an absolute dotted path, given file's package."""
    if level == 0:
        return (module or "").lower() or None
    drop = level - 1
    if drop > len(file_pkg):
        return None
    base = file_pkg[: len(file_pkg) - drop]
    parts = list(base)
    if module:
        parts.extend(module.split("."))
    return ".".join(p.lower() for p in parts) or None


def _iter_callers(tree: ast.AST) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Yield (caller_name, func_node) for every top-level func and class method."""
    for top in ast.iter_child_nodes(tree):
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield top.name, top
        elif isinstance(top, ast.ClassDef):
            for inner in top.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield inner.name, inner


def _local_shadows(func: ast.AST) -> set[str]:
    """Names assigned inside this function — they shadow any module-level binding."""
    shadows: set[str] = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign):
            for tgt in n.targets:
                if isinstance(tgt, ast.Name):
                    shadows.add(tgt.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            shadows.add(n.target.id)
    return shadows
