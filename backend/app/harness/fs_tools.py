"""Read-only filesystem tools for the agent (P25).

Gives the agent three tools to inspect the project without running Python:
  - read_file(path)      — read a file's content
  - glob_files(pattern)  — list files matching a glob
  - search_text(pattern, path) — grep-style text search

Safety: all paths are resolved against ``project_root``. Any path that would
escape the root returns {"ok": False, "error": "path_escape"}. Banned names
(.env, *.key, *.pem, .git, secrets/) also return an error.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_BANNED_NAMES = frozenset({".env", ".key", ".pem", "secrets", ".git"})
_BANNED_SUFFIXES = frozenset({".env", ".key", ".pem"})
_MAX_GLOB_RESULTS = 200
_MAX_SEARCH_RESULTS = 50
_MAX_FILE_CHARS = 50_000


class PathEscapeError(Exception):
    pass


class PathForbiddenError(Exception):
    pass


class FsTools:
    """Read-only filesystem access scoped to project_root."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()

    def _resolve(self, path_str: str) -> Path:
        """Resolve path relative to root, raising on escape or banned name."""
        resolved = (self._root / path_str).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise PathEscapeError(path_str)
        # Check each component for banned names/suffixes
        for part in resolved.parts:
            if part in _BANNED_NAMES or Path(part).suffix in _BANNED_SUFFIXES:
                raise PathForbiddenError(part)
        return resolved

    def read_file(self, args: dict[str, Any]) -> dict[str, Any]:
        path_str = str(args.get("path", ""))
        try:
            resolved = self._resolve(path_str)
        except PathEscapeError:
            return {"ok": False, "error": "path_escape"}
        except PathForbiddenError:
            return {"ok": False, "error": "path_forbidden"}
        if not resolved.exists():
            return {"ok": False, "error": f"not_found: {path_str}"}
        if not resolved.is_file():
            return {"ok": False, "error": "not_a_file"}
        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"ok": False, "error": f"read_error: {exc}"}
        if len(content) > _MAX_FILE_CHARS:
            content = content[:_MAX_FILE_CHARS] + "\n…(truncated)"
        return {
            "ok": True,
            "path": path_str,
            "content": content,
            "lines": content.count("\n") + 1,
        }

    def glob_files(self, args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pattern", "*"))
        # Detect escape attempts in the pattern itself
        if pattern.startswith("..") or "/../" in pattern or pattern.startswith("/"):
            return {"ok": False, "error": "path_escape"}
        try:
            matches = list(self._root.glob(pattern))
        except Exception as exc:
            return {"ok": False, "error": f"glob_error: {exc}"}
        # Filter banned and non-files
        files: list[str] = []
        for m in matches:
            if not m.is_file():
                continue
            rel = str(m.relative_to(self._root))
            if any(part in _BANNED_NAMES for part in m.parts):
                continue
            if m.suffix in _BANNED_SUFFIXES:
                continue
            files.append(rel)
            if len(files) >= _MAX_GLOB_RESULTS:
                break
        return {"ok": True, "files": files, "count": len(files)}

    def search_text(self, args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pattern", ""))
        path_str = str(args.get("path", "."))
        if path_str.startswith("..") or "/../" in path_str or path_str.startswith("/"):
            return {"ok": False, "error": "path_escape"}
        search_root = (self._root / path_str).resolve()
        if not str(search_root).startswith(str(self._root)):
            return {"ok": False, "error": "path_escape"}
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return {"ok": False, "error": f"invalid_regex: {exc}"}
        matches: list[dict[str, Any]] = []
        try:
            for fpath in search_root.rglob("*"):
                if not fpath.is_file():
                    continue
                if fpath.suffix in _BANNED_SUFFIXES:
                    continue
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if compiled.search(line):
                        matches.append({
                            "file": str(fpath.relative_to(self._root)),
                            "line": lineno,
                            "text": line[:200],
                        })
                        if len(matches) >= _MAX_SEARCH_RESULTS:
                            return {"ok": True, "matches": matches, "truncated": True}
        except Exception as exc:
            return {"ok": False, "error": f"search_error: {exc}"}
        return {"ok": True, "matches": matches, "truncated": False}
