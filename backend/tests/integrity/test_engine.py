from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

from backend.app.integrity.engine import IntegrityEngine
from backend.app.integrity.protocol import ScanContext, ScanResult


@dataclass
class _NoopPlugin:
    name: str = "noop"
    version: str = "0.1.0"
    depends_on: tuple[str, ...] = ()
    paths: tuple[str, ...] = ("**/*",)
    captured: ScanContext | None = None

    def scan(self, ctx: ScanContext) -> ScanResult:
        self.captured = ctx
        return ScanResult(plugin_name=self.name, plugin_version=self.version)


def _seed_graph(tmp_path: Path) -> None:
    g = tmp_path / "graphify"
    g.mkdir()
    (g / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))


def test_engine_runs_registered_plugins(tmp_path: Path) -> None:
    _seed_graph(tmp_path)
    engine = IntegrityEngine(repo_root=tmp_path)
    plugin = _NoopPlugin()
    engine.register(plugin)

    results = engine.run()

    assert len(results) == 1
    assert results[0].plugin_name == "noop"
    assert plugin.captured is not None
    assert plugin.captured.repo_root == tmp_path


def test_engine_run_with_no_plugins_returns_empty(tmp_path: Path) -> None:
    _seed_graph(tmp_path)
    engine = IntegrityEngine(repo_root=tmp_path)
    assert engine.run() == []
