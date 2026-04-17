from __future__ import annotations

from pathlib import Path

from .protocol import IntegrityPlugin, ScanContext, ScanResult
from .schema import GraphSnapshot


class IntegrityEngine:
    """Dispatches registered IntegrityPlugin instances against a graph snapshot."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._plugins: list[IntegrityPlugin] = []

    def register(self, plugin: IntegrityPlugin) -> None:
        self._plugins.append(plugin)

    def run(self) -> list[ScanResult]:
        if not self._plugins:
            return []
        graph = GraphSnapshot.load(self.repo_root)
        ctx = ScanContext(repo_root=self.repo_root, graph=graph)
        return [p.scan(ctx) for p in self._plugins]
