from __future__ import annotations

from pathlib import Path

from .issue import IntegrityIssue
from .protocol import IntegrityPlugin, ScanContext, ScanResult
from .schema import GraphSnapshot


class IntegrityEngine:
    """Dispatches registered IntegrityPlugin instances against a graph snapshot.

    Plugins run in dependency order (topologically sorted on `depends_on`).
    Exceptions raised during scan are caught and converted into ERROR issues
    on that plugin's ScanResult — sibling plugins continue.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._plugins: list[IntegrityPlugin] = []

    def register(self, plugin: IntegrityPlugin) -> None:
        self._plugins.append(plugin)

    def run(self) -> list[ScanResult]:
        if not self._plugins:
            return []
        ordered = self._topo_sort(self._plugins)
        graph = GraphSnapshot.load(self.repo_root)
        ctx = ScanContext(repo_root=self.repo_root, graph=graph)
        results: list[ScanResult] = []
        for plugin in ordered:
            results.append(self._safe_scan(plugin, ctx))
        return results

    def _safe_scan(self, plugin: IntegrityPlugin, ctx: ScanContext) -> ScanResult:
        try:
            return plugin.scan(ctx)
        except Exception as exc:
            issue = IntegrityIssue(
                rule="engine.plugin_failed",
                severity="ERROR",
                node_id=plugin.name,
                location=f"{plugin.name}.scan",
                message=f"{type(exc).__name__}: {exc}",
                evidence={"exception_type": type(exc).__name__},
                fix_class=None,
            )
            return ScanResult(
                plugin_name=plugin.name,
                plugin_version=getattr(plugin, "version", "unknown"),
                issues=[issue],
                failures=[f"{plugin.name}.scan: {exc}"],
            )

    @staticmethod
    def _topo_sort(plugins: list[IntegrityPlugin]) -> list[IntegrityPlugin]:
        by_name = {p.name: p for p in plugins}
        for p in plugins:
            for dep in p.depends_on:
                if dep not in by_name:
                    raise ValueError(f"Plugin {p.name!r} depends on unknown plugin {dep!r}")

        ordered: list[IntegrityPlugin] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(p: IntegrityPlugin) -> None:
            if p.name in visited:
                return
            if p.name in visiting:
                raise ValueError(f"circular dependency involving {p.name!r}")
            visiting.add(p.name)
            for dep in p.depends_on:
                visit(by_name[dep])
            visiting.discard(p.name)
            visited.add(p.name)
            ordered.append(p)

        for p in plugins:
            visit(p)
        return ordered
