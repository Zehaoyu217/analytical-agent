from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphSnapshot:
    """Read-only view of the stock graphify graph at scan time."""

    nodes: list[dict[str, Any]]
    links: list[dict[str, Any]]

    @classmethod
    def load(cls, repo_root: Path) -> "GraphSnapshot":
        graph_path = repo_root / "graphify" / "graph.json"
        data = json.loads(graph_path.read_text())
        return cls(nodes=data["nodes"], links=data["links"])
