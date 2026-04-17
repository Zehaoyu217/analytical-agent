import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from backend.app.integrity.engine import IntegrityEngine
from backend.app.integrity.issue import IntegrityIssue
from backend.app.integrity.protocol import ScanContext, ScanResult


@dataclass
class FakePlugin:
    name: str
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    issues_to_emit: list[IntegrityIssue] = field(default_factory=list)
    raise_on_scan: bool = False
    record: list[str] = field(default_factory=list)

    def scan(self, ctx: ScanContext) -> ScanResult:
        self.record.append(self.name)
        if self.raise_on_scan:
            raise RuntimeError(f"{self.name} blew up")
        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            issues=self.issues_to_emit,
        )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "graphify").mkdir()
    (tmp_path / "graphify" / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))
    return tmp_path


def test_dispatch_respects_depends_on(repo: Path):
    a = FakePlugin(name="a")
    b = FakePlugin(name="b", depends_on=("a",))
    c = FakePlugin(name="c", depends_on=("b",))
    engine = IntegrityEngine(repo)
    engine.register(c)
    engine.register(a)
    engine.register(b)
    results = engine.run()
    assert [r.plugin_name for r in results] == ["a", "b", "c"]


def test_plugin_exception_becomes_error_issue_and_siblings_continue(repo: Path):
    a = FakePlugin(name="a", raise_on_scan=True)
    b = FakePlugin(name="b")
    engine = IntegrityEngine(repo)
    engine.register(a)
    engine.register(b)
    results = engine.run()
    a_result = next(r for r in results if r.plugin_name == "a")
    assert any(i.severity == "ERROR" and "blew up" in i.message for i in a_result.issues)
    assert b.record == ["b"]
    assert "a.scan" in a_result.failures[0]


def test_circular_depends_on_raises(repo: Path):
    a = FakePlugin(name="a", depends_on=("b",))
    b = FakePlugin(name="b", depends_on=("a",))
    engine = IntegrityEngine(repo)
    engine.register(a)
    engine.register(b)
    with pytest.raises(ValueError, match="circular"):
        engine.run()


def test_unknown_dependency_raises(repo: Path):
    a = FakePlugin(name="a", depends_on=("nonexistent",))
    engine = IntegrityEngine(repo)
    engine.register(a)
    with pytest.raises(ValueError, match="nonexistent"):
        engine.run()
