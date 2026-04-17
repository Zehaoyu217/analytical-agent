from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ...schema import GraphSnapshot

USE_RELATIONS = frozenset({
    "imports_from", "calls", "implements", "extends", "instantiates",
    "uses", "references", "decorated_by", "raises", "returns", "routes_to",
})

ENTRY_PREFIXES = (
    "main_", "app_main", "conftest", "cli_", "settings",
    "__init__", "vite_config", "tailwind_config", "pyproject", "package_json",
)


def _is_entry_or_skip(node: dict) -> bool:
    src = node.get("source_file", "") or ""
    nid = node["id"]
    if "/tests/" in src or src.endswith("_test.py") or ".test." in src:
        return True
    if "__tests__" in src or "/e2e/" in src:
        return True
    if any(nid.startswith(p) for p in ENTRY_PREFIXES):
        return True
    if src.endswith("/main.py") or src.endswith("/__init__.py"):
        return True
    if "/migrations/" in src:
        return True
    return src.endswith((".md", ".json", ".yaml", ".yml", ".html", ".css", ".svg"))


def find_orphans(graph: GraphSnapshot, *, exclude_paths: Iterable[str] | None = None) -> list[str]:
    """Return IDs of code-file nodes with no inbound EXTRACTED USE_RELATIONS edges."""
    inbound: dict[str, set[str]] = defaultdict(set)
    for link in graph.links:
        if link.get("confidence") != "EXTRACTED":
            continue
        if link.get("relation") not in USE_RELATIONS:
            continue
        inbound[link["target"]].add(link["source"])

    out: list[str] = []
    for node in graph.nodes:
        if node.get("file_type") != "code":
            continue
        if _is_entry_or_skip(node):
            continue
        if inbound[node["id"]]:
            continue
        out.append(node["id"])
    return out
