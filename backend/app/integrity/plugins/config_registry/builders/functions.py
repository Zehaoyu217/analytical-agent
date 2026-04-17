"""FunctionsBuilder — AST extraction of @router/@app + FastAPI event handlers.

Uses Python ``ast`` (no runtime imports), so syntax errors yield
a per-file failure entry without crashing the scan.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FunctionEntry:
    id: str
    path: str
    line: int
    decorator: str
    target: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "path": self.path, "line": self.line,
                "decorator": self.decorator, "target": self.target}


def _module_dotted_path(rel_path: str) -> str:
    """``"backend/app/api/foo_api.py"`` → ``"backend.app.api.foo_api"``."""
    if rel_path.endswith(".py"):
        rel_path = rel_path[:-3]
    if rel_path.endswith("/__init__"):
        rel_path = rel_path[:-len("/__init__")]
    return rel_path.replace("/", ".")


def _first_string_arg(call: ast.Call) -> str | None:
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _extract_decorator(
    deco: ast.expr,
    allowed_names: set[str],
    event_handlers: set[str],
) -> tuple[str, str] | None:
    """Return (decorator_name, target) if decorator matches, else None."""
    # @router.post("/x")
    if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
        attr = deco.func
        if isinstance(attr.value, ast.Name) and attr.value.id in allowed_names:
            decorator_name = f"{attr.value.id}.{attr.attr}"
            # @app.on_event("startup") special-case
            if attr.attr == "on_event":
                target = _first_string_arg(deco) or ""
                if target in event_handlers:
                    return decorator_name, target
                return None
            target = _first_string_arg(deco) or ""
            return decorator_name, target
    return None


class FunctionsBuilder:
    def __init__(
        self,
        repo_root: Path,
        search_globs: list[str],
        decorators: list[str],
        event_handlers: list[str],
    ) -> None:
        self.repo_root = repo_root
        self.search_globs = list(search_globs)
        self.decorators = set(decorators)
        self.event_handlers = set(event_handlers)

    def build(self) -> tuple[list[FunctionEntry], list[str]]:
        entries: list[FunctionEntry] = []
        failures: list[str] = []

        seen_paths: set[Path] = set()
        for pattern in self.search_globs:
            for path in sorted(self.repo_root.glob(pattern)):
                if not path.is_file() or path in seen_paths:
                    continue
                seen_paths.add(path)
                self._scan_file(path, entries, failures)

        entries.sort(key=lambda e: e.id)
        return entries, failures

    def _scan_file(
        self,
        path: Path,
        entries: list[FunctionEntry],
        failures: list[str],
    ) -> None:
        rel = path.relative_to(self.repo_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            failures.append(f"functions:{rel}: {type(exc).__name__}: {exc}")
            return

        module_dotted = _module_dotted_path(rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for deco in node.decorator_list:
                match = _extract_decorator(deco, self.decorators, self.event_handlers)
                if match is None:
                    continue
                decorator_name, target = match
                entries.append(FunctionEntry(
                    id=f"{module_dotted}.{node.name}",
                    path=rel,
                    line=node.lineno,
                    decorator=decorator_name,
                    target=target,
                ))
