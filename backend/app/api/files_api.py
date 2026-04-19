"""REST endpoints for sandboxed file tree browsing and reading.

All access is confined to a configurable safe root (`FILES_ROOT` env var,
defaults to `data/files`). Paths are validated against the canonical root
after resolution so that symlink-escapes and `..` traversals are rejected.
Single-process assumption.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/files", tags=["files"])

_FILE_READ_CAP_BYTES = 10 * 1024 * 1024  # 10 MB
_TREE_ENTRIES_CAP = 5000


class FileNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str          # POSIX path relative to root, no leading "/"
    name: str
    kind: Literal["file", "dir"]
    size: int | None   # bytes for files, None for dirs
    modified: float


class FileTreeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    root: str          # always "" (the safe root)
    entries: list[FileNode]
    truncated: bool


class FileReadResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    size: int
    content: str
    encoding: Literal["utf-8", "base64"]


def _files_root() -> Path:
    root = Path(os.environ.get("FILES_ROOT", "data/files"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reject_unsafe_input(user_path: str) -> None:
    if "\x00" in user_path:
        raise HTTPException(status_code=400, detail="null byte in path")
    if ".." in user_path.split("/") or ".." in user_path.split("\\"):
        raise HTTPException(status_code=400, detail="parent traversal not allowed")
    if user_path.startswith("/") or user_path.startswith("\\"):
        raise HTTPException(status_code=400, detail="absolute paths not allowed")
    # Windows drive letter guard (e.g. C:\...). Cheap and consistent.
    if len(user_path) >= 2 and user_path[1] == ":":
        raise HTTPException(status_code=400, detail="absolute paths not allowed")


def _resolve_within_root(user_path: str) -> Path:
    """Return the absolute resolved path, ensuring it stays within the safe root.

    Rejects traversal, absolute paths, null bytes, and symlink escapes.
    """
    _reject_unsafe_input(user_path)
    root = _files_root().resolve()
    candidate = (root / user_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path escapes safe root") from exc
    return candidate


def _posix_rel(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    # Explicit POSIX formatting so Windows backslashes never leak out.
    return rel.as_posix()


def _build_node(path: Path, root: Path) -> FileNode:
    stat = path.stat()
    kind: Literal["file", "dir"] = "dir" if path.is_dir() else "file"
    return FileNode(
        path=_posix_rel(path, root),
        name=path.name,
        kind=kind,
        size=None if kind == "dir" else stat.st_size,
        modified=stat.st_mtime,
    )


@router.get("/tree")
def get_tree(path: str = Query(default="")) -> FileTreeResponse:
    root = _files_root().resolve()
    target = _resolve_within_root(path) if path else root
    if not target.exists():
        raise HTTPException(status_code=404, detail="path not found")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    entries: list[FileNode] = []
    truncated = False
    # Sort for deterministic output: dirs before files, then name.
    children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for child in children:
        # Symlink escape guard: resolved child must still be within root.
        try:
            resolved = child.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if len(entries) >= _TREE_ENTRIES_CAP:
            truncated = True
            break
        entries.append(_build_node(child, root))

    return FileTreeResponse(root="", entries=entries, truncated=truncated)


@router.get("/read")
def read_file(
    path: str = Query(...),
    include_binary_content: bool = Query(default=False),
) -> FileReadResponse:
    """Read a file from inside the safe root.

    Text files (valid UTF-8) always return content. Binary files return an
    empty `content` by default — the current UI only shows a metadata line
    for binary blobs, and shipping a 13 MB base64 payload just to render
    "Binary file — N bytes" is pure waste on slow links.

    Callers that truly need the bytes (e.g. a future download or preview
    surface) can opt in with `?include_binary_content=1`.
    """
    if not path:
        raise HTTPException(status_code=400, detail="path required")
    target = _resolve_within_root(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="file not found")
    if target.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")

    size = target.stat().st_size
    if size > _FILE_READ_CAP_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds read cap")

    data = target.read_bytes()
    rel_path = _posix_rel(target, _files_root().resolve())
    try:
        text = data.decode("utf-8")
        return FileReadResponse(
            path=rel_path,
            size=size,
            content=text,
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        encoded = base64.b64encode(data).decode("ascii") if include_binary_content else ""
        return FileReadResponse(
            path=rel_path,
            size=size,
            content=encoded,
            encoding="base64",
        )
