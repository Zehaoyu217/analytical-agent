"""Read-only REST endpoints for the Knowledge-surface file tree.

Powers the Knowledge surface: file tree, page reader, backlinks. Content
is plain markdown on disk, so these endpoints are pure file-system reads
with strict path containment to prevent traversal.

Root resolution (first match wins):
  1. ``$WIKI_ROOT`` env override (explicit)
  2. ``$LLM_WIKI_DIR`` — a user-installed llm_wiki project directory.
     When set, its Obsidian-style vault becomes the Knowledge page root
     so the two-stage analyze→generate wiki (entities/, concepts/,
     sources/ pages with ``[[wikilinks]]``) is what the user browses.
  3. ``SECOND_BRAIN_HOME`` when ``SECOND_BRAIN_ENABLED`` — legacy SB KB
     (sources/, claims/, digests/, log.md).
  4. ``knowledge/wiki/`` repo-internal default (agent scratchpad).
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/wiki", tags=["wiki"])

_WIKI_ROOT_ENV = "WIKI_ROOT"
_LLM_WIKI_DIR_ENV = "LLM_WIKI_DIR"
_DEFAULT_WIKI_ROOT = Path("knowledge/wiki")
_PINNED = ("index.md", "working.md", "log.md")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]*)?\)")


def _wiki_root() -> Path:
    override = os.environ.get(_WIKI_ROOT_ENV)
    if override:
        return Path(override).resolve()
    # Late import — avoids a circular dependency at module load time and
    # lets feature flags change at runtime without a reimport.
    from app import config as _app_config  # noqa: PLC0415

    # llm_wiki sidecar wins over SB legacy when both are configured — the
    # sidecar is the current extraction path; SB is read-mostly legacy.
    llm_wiki = os.environ.get(_LLM_WIKI_DIR_ENV) or getattr(
        _app_config.get_config(), "llm_wiki_dir", "",
    )
    if llm_wiki:
        path = Path(llm_wiki).expanduser().resolve()
        if path.exists():
            return path

    if getattr(_app_config, "SECOND_BRAIN_ENABLED", False):
        return _app_config.SECOND_BRAIN_HOME.resolve()
    return _DEFAULT_WIKI_ROOT.resolve()


def _safe_resolve(rel_path: str) -> Path:
    """Resolve `rel_path` under the wiki root, rejecting traversal."""
    root = _wiki_root()
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path escapes wiki root") from exc
    return candidate


@dataclass(frozen=True)
class WikiNode:
    name: str
    path: str  # relative to wiki root, posix-style
    kind: str  # "dir" | "file"
    size: int = 0
    modified: float = 0.0
    children: tuple[WikiNode, ...] = ()
    pinned: bool = False


def _walk(dir_path: Path, root: Path) -> list[WikiNode]:
    nodes: list[WikiNode] = []
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return nodes
    for entry in entries:
        if entry.name.startswith("."):
            continue
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            children = _walk(entry, root)
            if not children:
                continue
            nodes.append(WikiNode(name=entry.name, path=rel, kind="dir", children=tuple(children)))
        elif entry.suffix.lower() == ".md":
            stat = entry.stat()
            nodes.append(
                WikiNode(
                    name=entry.name,
                    path=rel,
                    kind="file",
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    pinned=entry.name in _PINNED and entry.parent == root,
                )
            )
    return nodes


def _node_to_dict(node: WikiNode) -> dict[str, Any]:
    d = asdict(node)
    d["children"] = [_node_to_dict(c) for c in node.children]
    return d


@router.get("/tree")
def get_tree() -> dict[str, Any]:
    root = _wiki_root()
    if not root.exists():
        return {"root": str(root), "nodes": []}
    nodes = _walk(root, root)
    return {"root": str(root), "nodes": [_node_to_dict(n) for n in nodes]}


@router.get("/page")
def get_page(path: str = Query(..., min_length=1, max_length=512)) -> dict[str, Any]:
    target = _safe_resolve(path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    if target.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="not a markdown file")
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    stat = target.stat()
    outbound = sorted({m.group(2) for m in _LINK_RE.finditer(content)})
    return {
        "path": target.relative_to(_wiki_root()).as_posix(),
        "content": content,
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "outbound_links": outbound,
    }


@router.get("/backlinks")
def get_backlinks(path: str = Query(..., min_length=1, max_length=512)) -> dict[str, Any]:
    """Files that link to `path`. Cheap grep — fine for wiki sizes."""
    target = _safe_resolve(path)
    target_name = target.name
    root = _wiki_root()
    refs: list[dict[str, str]] = []
    if not root.exists():
        return {"path": path, "backlinks": []}
    for md in root.rglob("*.md"):
        if md == target:
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if target_name in text:
            for m in _LINK_RE.finditer(text):
                if m.group(2).endswith(target_name):
                    refs.append(
                        {
                            "path": md.relative_to(root).as_posix(),
                            "label": m.group(1),
                        }
                    )
                    break
    return {"path": path, "backlinks": refs}
