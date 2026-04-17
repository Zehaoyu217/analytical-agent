# Plugin B — Graph Lint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship gate β of the integrity system: Plugin B (`graph_lint`) emits 5 rule classes, the engine becomes the real orchestrator (auto-merges A's augmented graph, dispatches A→B, aggregates reports), and the frontend gets a discoverable Health page rendering `docs/health/latest.md`.

**Architecture:** The engine reads `graph.json` + auto-merges `graph.augmented.json` into a `GraphSnapshot`, then dispatches plugins in dependency order. Plugin B intersects vulture + knip + graph-orphan signals for `dead_code`, diffs against dated snapshots in `integrity-out/snapshots/` for drift/WoW rules, and walks the merged graph for `handler_unbound`. A new `report.py` aggregator writes `integrity-out/{date}/report.{json,md}` plus committed `docs/health/{latest,trend}.md` for visibility. Frontend mounts a new `health` section in the existing zustand-driven IconRail; the markdown is served by a FastAPI `StaticFiles` mount of `docs/health/`.

**Tech Stack:** Python 3.12 (FastAPI, Pydantic), `vulture` (Python dead-code), `knip` (TS/JS dead-code), React + Zustand (frontend), pytest, Playwright.

---

## File Structure

### Backend — new files

| Path | Purpose |
|------|---------|
| `backend/app/integrity/__main__.py` | Module CLI: `python -m backend.app.integrity [--plugin <name>] [--no-augment]` |
| `backend/app/integrity/config.py` | Loads `config/integrity.yaml`; applies `INTEGRITY_*` env overrides |
| `backend/app/integrity/snapshots.py` | `write_snapshot`, `load_snapshot_by_age`, `prune_older_than` |
| `backend/app/integrity/report.py` | Aggregates `ScanResult`s → `report.json/.md` + `docs/health/latest.md` + appends `trend.md` |
| `backend/app/integrity/issue.py` | Frozen `IntegrityIssue` dataclass with stable `dedup_key()` and `first_seen` carry-forward helper |
| `backend/app/integrity/plugins/graph_lint/__init__.py` | Package marker |
| `backend/app/integrity/plugins/graph_lint/__main__.py` | Standalone CLI for B alone (mirrors Plugin A's standalone entry) |
| `backend/app/integrity/plugins/graph_lint/plugin.py` | `GraphLintPlugin` dataclass; orchestrates rules |
| `backend/app/integrity/plugins/graph_lint/orphans.py` | Computes graph orphans on the merged graph (shared by `dead_code`) |
| `backend/app/integrity/plugins/graph_lint/git_renames.py` | `git log --diff-filter=R` parser for `drift_removed` downgrade |
| `backend/app/integrity/plugins/graph_lint/rules/__init__.py` | Package marker |
| `backend/app/integrity/plugins/graph_lint/rules/dead_code.py` | Triple-intersection rule |
| `backend/app/integrity/plugins/graph_lint/rules/drift.py` | `drift_added` + `drift_removed` |
| `backend/app/integrity/plugins/graph_lint/rules/density_drop.py` | Per-module WoW density compare |
| `backend/app/integrity/plugins/graph_lint/rules/orphan_growth.py` | Whole-graph WoW orphan compare |
| `backend/app/integrity/plugins/graph_lint/rules/handler_unbound.py` | FastAPI route w/o `routes_to` edge |
| `backend/app/integrity/plugins/graph_lint/wrappers/__init__.py` | Package marker |
| `backend/app/integrity/plugins/graph_lint/wrappers/vulture.py` | Subprocess wrapper for `vulture --json` |
| `backend/app/integrity/plugins/graph_lint/wrappers/knip.py` | Subprocess wrapper for `npx knip --reporter json` |
| `backend/tests/integrity/test_engine_pipeline.py` | A→B pipeline integration test |
| `backend/tests/integrity/test_graph_snapshot_merge.py` | `GraphSnapshot.load` augmented-merge test |
| `backend/tests/integrity/test_snapshots.py` | Snapshot module tests |
| `backend/tests/integrity/test_report.py` | Report aggregator tests |
| `backend/tests/integrity/test_config.py` | Config loader tests |
| `backend/tests/integrity/test_issue.py` | `IntegrityIssue` dedup + first-seen tests |
| `backend/tests/integrity/test_main_cli.py` | `python -m backend.app.integrity` CLI tests |
| `backend/tests/integrity/plugins/graph_lint/test_plugin.py` | Plugin shell + scan integration test |
| `backend/tests/integrity/plugins/graph_lint/test_orphans.py` | Orphan helper tests |
| `backend/tests/integrity/plugins/graph_lint/test_git_renames.py` | Git rename parser tests |
| `backend/tests/integrity/plugins/graph_lint/rules/test_dead_code.py` | Dead-code rule tests |
| `backend/tests/integrity/plugins/graph_lint/rules/test_drift.py` | Drift rule tests |
| `backend/tests/integrity/plugins/graph_lint/rules/test_density_drop.py` | Density rule tests |
| `backend/tests/integrity/plugins/graph_lint/rules/test_orphan_growth.py` | Orphan growth rule tests |
| `backend/tests/integrity/plugins/graph_lint/rules/test_handler_unbound.py` | Handler-unbound rule tests |
| `backend/tests/integrity/plugins/graph_lint/wrappers/test_vulture.py` | Vulture wrapper tests |
| `backend/tests/integrity/plugins/graph_lint/wrappers/test_knip.py` | Knip wrapper tests |

### Backend — modified files

| Path | Change |
|------|--------|
| `backend/app/integrity/schema.py` | `GraphSnapshot.load` auto-merges `graph.augmented.json` |
| `backend/app/integrity/protocol.py` | `ScanResult.issues` typed as `list[IntegrityIssue]` (still serializable to dict) |
| `backend/app/integrity/engine.py` | `register_default_plugins`, dependency-ordered dispatch, exception catching, snapshot + report write |
| `backend/app/main.py` | Mount `StaticFiles(directory="docs/health")` at `/static/health` |
| `backend/pyproject.toml` | Add `vulture` + `pyyaml` to dev / dependencies |

### Frontend — new files

| Path | Purpose |
|------|---------|
| `frontend/src/sections/HealthSection.tsx` | Renders `docs/health/latest.md` via `MarkdownContent` |
| `frontend/src/sections/__tests__/HealthSection.test.tsx` | Unit test for HealthSection rendering |
| `frontend/e2e/health.spec.ts` | Playwright E2E test for the Health rail entry + page |

### Frontend — modified files

| Path | Change |
|------|--------|
| `frontend/src/lib/store.ts` | Add `'health'` to `SectionId` union |
| `frontend/src/components/layout/IconRail.tsx` | Add Health entry between Context and Settings |
| `frontend/src/App.tsx` | Add `case 'health'` to section switch |
| `frontend/package.json` | Add `knip` to `devDependencies` |
| `frontend/knip.json` | New file — knip config (entry points, ignored paths) |

### Repo-level

| Path | Change |
|------|--------|
| `config/integrity.yaml` | New file — engine config (committed) |
| `.gitignore` | Add `integrity-out/` |
| `Makefile` | Add `integrity:` (full pipeline), `integrity-lint:` (B only), `integrity-snapshot-prune:` |
| `docs/health/audit-2026-04-17.md` | New file — gate β manual dead-code audit results |
| `docs/log.md` | Append `[Unreleased]` entry for gate β |

---

## Task 1: IntegrityIssue dataclass + dedup helper

**Files:**
- Create: `backend/app/integrity/issue.py`
- Test: `backend/tests/integrity/test_issue.py`

This unifies the issue shape across plugins (currently `ScanResult.issues: list[dict]`). `dedup_key()` + `carry_first_seen()` enable stable `first_seen` dates across runs without storing extra state.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_issue.py
from backend.app.integrity.issue import IntegrityIssue, carry_first_seen


def make_issue(rule: str, node_id: str, first_seen: str = "2026-04-17") -> IntegrityIssue:
    return IntegrityIssue(
        rule=rule,
        severity="WARN",
        node_id=node_id,
        location="x.py:1",
        message="m",
        evidence={},
        fix_class=None,
        first_seen=first_seen,
    )


def test_dedup_key_combines_rule_and_node_id():
    a = make_issue("graph.dead_code", "mod_fn")
    b = make_issue("graph.drift_added", "mod_fn")
    c = make_issue("graph.dead_code", "mod_fn")
    assert a.dedup_key() != b.dedup_key()
    assert a.dedup_key() == c.dedup_key()


def test_carry_first_seen_preserves_prior_date():
    prior = [make_issue("graph.dead_code", "mod_fn", first_seen="2026-04-10")]
    today = [make_issue("graph.dead_code", "mod_fn", first_seen="2026-04-17")]
    out = carry_first_seen(today, prior)
    assert out[0].first_seen == "2026-04-10"


def test_carry_first_seen_keeps_today_when_new():
    prior: list[IntegrityIssue] = []
    today = [make_issue("graph.dead_code", "fresh_node", first_seen="2026-04-17")]
    out = carry_first_seen(today, prior)
    assert out[0].first_seen == "2026-04-17"


def test_serialize_roundtrip():
    a = make_issue("graph.dead_code", "mod_fn")
    d = a.to_dict()
    b = IntegrityIssue.from_dict(d)
    assert a == b
```

- [ ] **Step 2: Run to confirm it fails**

```
uv run pytest backend/tests/integrity/test_issue.py -v
```
Expected: ImportError — module doesn't exist.

- [ ] **Step 3: Implement `IntegrityIssue`**

```python
# backend/app/integrity/issue.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["INFO", "WARN", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class IntegrityIssue:
    rule: str
    severity: Severity
    node_id: str
    location: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    fix_class: str | None = None
    first_seen: str = ""

    def dedup_key(self) -> tuple[str, str]:
        return (self.rule, self.node_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntegrityIssue":
        return cls(
            rule=d["rule"],
            severity=d["severity"],
            node_id=d["node_id"],
            location=d["location"],
            message=d["message"],
            evidence=dict(d.get("evidence", {})),
            fix_class=d.get("fix_class"),
            first_seen=d.get("first_seen", ""),
        )


def carry_first_seen(
    today: list[IntegrityIssue],
    prior: list[IntegrityIssue],
) -> list[IntegrityIssue]:
    prior_by_key = {p.dedup_key(): p.first_seen for p in prior}
    out: list[IntegrityIssue] = []
    for issue in today:
        prior_first = prior_by_key.get(issue.dedup_key())
        if prior_first:
            out.append(IntegrityIssue.from_dict({**issue.to_dict(), "first_seen": prior_first}))
        else:
            out.append(issue)
    return out
```

- [ ] **Step 4: Run to confirm it passes**

```
uv run pytest backend/tests/integrity/test_issue.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/issue.py backend/tests/integrity/test_issue.py
git commit -m "feat(integrity): add IntegrityIssue dataclass with dedup + first-seen carry"
```

---

## Task 2: GraphSnapshot.load — auto-merge augmented graph

**Files:**
- Modify: `backend/app/integrity/schema.py`
- Test: `backend/tests/integrity/test_graph_snapshot_merge.py`

Augmented nodes/links must be merged into `GraphSnapshot` automatically. Augmented nodes win on duplicate `id`; augmented links concatenate after dedupe on `(source, target, relation)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_graph_snapshot_merge.py
import json
from pathlib import Path

import pytest

from backend.app.integrity.schema import GraphSnapshot


@pytest.fixture
def repo_with_graphs(tmp_path: Path) -> Path:
    (tmp_path / "graphify").mkdir()
    base = {
        "nodes": [
            {"id": "a", "label": "a", "kind": "function", "source_file": "x.py"},
            {"id": "b", "label": "b", "kind": "function", "source_file": "x.py"},
        ],
        "links": [
            {"source": "a", "target": "b", "relation": "calls", "confidence": "EXTRACTED"},
        ],
    }
    (tmp_path / "graphify" / "graph.json").write_text(json.dumps(base))
    return tmp_path


def test_loads_base_when_no_augmented(repo_with_graphs: Path):
    g = GraphSnapshot.load(repo_with_graphs)
    assert {n["id"] for n in g.nodes} == {"a", "b"}
    assert len(g.links) == 1


def test_merges_augmented_nodes(repo_with_graphs: Path):
    aug = {
        "nodes": [{"id": "c", "label": "c", "kind": "function", "source_file": "y.py"}],
        "links": [{"source": "a", "target": "c", "relation": "calls", "confidence": "EXTRACTED"}],
    }
    (repo_with_graphs / "graphify" / "graph.augmented.json").write_text(json.dumps(aug))
    g = GraphSnapshot.load(repo_with_graphs)
    assert {n["id"] for n in g.nodes} == {"a", "b", "c"}
    assert len(g.links) == 2


def test_augmented_node_wins_on_duplicate_id(repo_with_graphs: Path):
    aug = {
        "nodes": [{"id": "a", "label": "A_AUGMENTED", "kind": "function", "source_file": "x.py"}],
        "links": [],
    }
    (repo_with_graphs / "graphify" / "graph.augmented.json").write_text(json.dumps(aug))
    g = GraphSnapshot.load(repo_with_graphs)
    a_node = next(n for n in g.nodes if n["id"] == "a")
    assert a_node["label"] == "A_AUGMENTED"


def test_link_dedupe_on_source_target_relation(repo_with_graphs: Path):
    aug = {
        "nodes": [],
        "links": [
            {"source": "a", "target": "b", "relation": "calls", "confidence": "EXTRACTED"},  # dup
            {"source": "a", "target": "b", "relation": "imports_from", "confidence": "EXTRACTED"},  # not dup
        ],
    }
    (repo_with_graphs / "graphify" / "graph.augmented.json").write_text(json.dumps(aug))
    g = GraphSnapshot.load(repo_with_graphs)
    assert len(g.links) == 2
    relations = sorted(link["relation"] for link in g.links)
    assert relations == ["calls", "imports_from"]
```

- [ ] **Step 2: Run to confirm it fails**

```
uv run pytest backend/tests/integrity/test_graph_snapshot_merge.py -v
```
Expected: tests pass for base load (already implemented), fail for augmented merge.

- [ ] **Step 3: Implement auto-merge**

```python
# backend/app/integrity/schema.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphSnapshot:
    """Read-only view of the merged graphify + augmented graph at scan time."""

    nodes: list[dict[str, Any]]
    links: list[dict[str, Any]]

    @classmethod
    def load(cls, repo_root: Path) -> "GraphSnapshot":
        graph_path = repo_root / "graphify" / "graph.json"
        base = json.loads(graph_path.read_text())
        nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in base["nodes"]}
        link_keys: set[tuple[str, str, str]] = set()
        links: list[dict[str, Any]] = []
        for link in base["links"]:
            key = (link["source"], link["target"], link.get("relation", ""))
            if key in link_keys:
                continue
            link_keys.add(key)
            links.append(link)

        aug_path = repo_root / "graphify" / "graph.augmented.json"
        if aug_path.exists():
            aug = json.loads(aug_path.read_text())
            for node in aug.get("nodes", []):
                nodes_by_id[node["id"]] = node  # augmented wins
            for link in aug.get("links", []):
                key = (link["source"], link["target"], link.get("relation", ""))
                if key in link_keys:
                    continue
                link_keys.add(key)
                links.append(link)

        return cls(nodes=list(nodes_by_id.values()), links=links)
```

- [ ] **Step 4: Run to confirm it passes**

```
uv run pytest backend/tests/integrity/test_graph_snapshot_merge.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run prior integrity tests to confirm no regression**

```
uv run pytest backend/tests/integrity/ -q
```
Expected: All previously-passing tests still pass (77 + 4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/schema.py backend/tests/integrity/test_graph_snapshot_merge.py
git commit -m "feat(integrity): GraphSnapshot.load auto-merges augmented graph"
```

---

## Task 3: Engine — dependency-ordered dispatch + exception catching

**Files:**
- Modify: `backend/app/integrity/engine.py`
- Modify: `backend/app/integrity/protocol.py`
- Test: `backend/tests/integrity/test_engine_pipeline.py` (subset for dispatch logic only — full pipeline test in Task 19)

Dispatch order respects `depends_on`. Plugin `scan()` exceptions don't crash siblings — they convert to a `severity=ERROR` issue.

- [ ] **Step 1: Update `protocol.py` ScanResult to type issues**

```python
# backend/app/integrity/protocol.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from .issue import IntegrityIssue
from .schema import GraphSnapshot


@dataclass(frozen=True)
class ScanContext:
    repo_root: Path
    graph: GraphSnapshot


@dataclass(frozen=True)
class ScanResult:
    plugin_name: str
    plugin_version: str
    issues: list[IntegrityIssue] = field(default_factory=list)
    artifacts: list[Path] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@runtime_checkable
class IntegrityPlugin(Protocol):
    name: str
    version: str
    depends_on: tuple[str, ...]
    paths: tuple[str, ...]

    def scan(self, ctx: ScanContext) -> ScanResult: ...
```

- [ ] **Step 2: Write the failing engine test**

```python
# backend/tests/integrity/test_engine_pipeline.py
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
        return ScanResult(plugin_name=self.name, plugin_version=self.version, issues=self.issues_to_emit)


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
    b_result = next(r for r in results if r.plugin_name == "b")
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
```

- [ ] **Step 3: Run to confirm failures**

```
uv run pytest backend/tests/integrity/test_engine_pipeline.py -v
```
Expected: 4 failures (current engine has no dependency ordering, no exception catching, no validation).

- [ ] **Step 4: Implement engine**

```python
# backend/app/integrity/engine.py
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
```

- [ ] **Step 5: Run to confirm passes**

```
uv run pytest backend/tests/integrity/test_engine_pipeline.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Update Plugin A's ScanResult to use IntegrityIssue (no behavior change — issues currently empty list)**

The graph_extension plugin currently emits `ScanResult` with no issues. Confirm it still type-checks:

```
uv run pytest backend/tests/integrity/ -q
```
Expected: all previous + 4 new = 81 passed (or close — exact count depends on prior state).

- [ ] **Step 7: Commit**

```bash
git add backend/app/integrity/engine.py backend/app/integrity/protocol.py backend/tests/integrity/test_engine_pipeline.py
git commit -m "feat(integrity): engine does topo-sort dispatch + catches plugin exceptions"
```

---

## Task 4: Snapshots module

**Files:**
- Create: `backend/app/integrity/snapshots.py`
- Test: `backend/tests/integrity/test_snapshots.py`

Snapshot files live under `integrity-out/snapshots/{ISO-date}.json` (gitignored). API: `write_snapshot`, `load_snapshot_by_age`, `prune_older_than`. Atomic write via `tempfile + rename`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_snapshots.py
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.app.integrity.snapshots import (
    load_snapshot_by_age,
    prune_older_than,
    snapshot_path,
    write_snapshot,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_write_creates_dated_file(repo: Path):
    payload = {"nodes": [{"id": "a"}], "links": []}
    out = write_snapshot(repo, payload, today=date(2026, 4, 17))
    assert out == repo / "integrity-out" / "snapshots" / "2026-04-17.json"
    assert json.loads(out.read_text()) == payload


def test_write_is_atomic(repo: Path, monkeypatch):
    payload = {"nodes": [], "links": []}
    p = write_snapshot(repo, payload, today=date(2026, 4, 17))
    # No partial / temp files should remain alongside the final file
    siblings = list(p.parent.iterdir())
    assert siblings == [p]


def test_load_by_age_returns_correct_snapshot(repo: Path):
    write_snapshot(repo, {"nodes": [{"id": "yesterday"}], "links": []}, today=date(2026, 4, 16))
    write_snapshot(repo, {"nodes": [{"id": "weekago"}], "links": []}, today=date(2026, 4, 10))
    today = date(2026, 4, 17)
    yest = load_snapshot_by_age(repo, days=1, today=today)
    week = load_snapshot_by_age(repo, days=7, today=today)
    assert yest is not None and yest["nodes"][0]["id"] == "yesterday"
    assert week is not None and week["nodes"][0]["id"] == "weekago"


def test_load_by_age_returns_none_when_missing(repo: Path):
    today = date(2026, 4, 17)
    assert load_snapshot_by_age(repo, days=1, today=today) is None


def test_prune_removes_older_than_n_days(repo: Path):
    today = date(2026, 4, 17)
    for i in range(0, 35, 5):
        write_snapshot(repo, {"nodes": [], "links": []}, today=today - timedelta(days=i))
    removed = prune_older_than(repo, days=30, today=today)
    assert removed == 1  # only the 35-day-old one
    remaining = sorted(p.name for p in (repo / "integrity-out" / "snapshots").iterdir())
    assert "2026-03-13.json" not in remaining


def test_snapshot_path_uses_iso_date(repo: Path):
    p = snapshot_path(repo, date(2026, 4, 17))
    assert p.name == "2026-04-17.json"
```

- [ ] **Step 2: Run to confirm it fails**

```
uv run pytest backend/tests/integrity/test_snapshots.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement snapshots module**

```python
# backend/app/integrity/snapshots.py
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def _snapshots_dir(repo_root: Path) -> Path:
    d = repo_root / "integrity-out" / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def snapshot_path(repo_root: Path, day: date) -> Path:
    return _snapshots_dir(repo_root) / f"{day.isoformat()}.json"


def write_snapshot(
    repo_root: Path, payload: dict[str, Any], today: date
) -> Path:
    final = snapshot_path(repo_root, today)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".snapshot-", suffix=".json", dir=str(final.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        os.replace(tmp_path_str, final)
    except Exception:
        Path(tmp_path_str).unlink(missing_ok=True)
        raise
    return final


def load_snapshot_by_age(
    repo_root: Path, days: int, today: date
) -> dict[str, Any] | None:
    target = today - timedelta(days=days)
    p = snapshot_path(repo_root, target)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def prune_older_than(repo_root: Path, days: int, today: date) -> int:
    cutoff = today - timedelta(days=days)
    removed = 0
    for snap in _snapshots_dir(repo_root).glob("*.json"):
        try:
            day = date.fromisoformat(snap.stem)
        except ValueError:
            continue
        if day < cutoff:
            snap.unlink()
            removed += 1
    return removed
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/test_snapshots.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/snapshots.py backend/tests/integrity/test_snapshots.py
git commit -m "feat(integrity): snapshots module — atomic write, age-based load, prune"
```

---

## Task 5: Config module

**Files:**
- Create: `backend/app/integrity/config.py`
- Test: `backend/tests/integrity/test_config.py`

Loads `config/integrity.yaml`. Applies env overrides: `INTEGRITY_<KEY>=<value>` overrides any leaf threshold (uppercased dotted path → flat). Parses ints/floats, leaves strings.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_config.py
from pathlib import Path

import pytest

from backend.app.integrity.config import IntegrityConfig, load_config


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_load_returns_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg.plugins["graph_extension"]["enabled"] is True
    assert cfg.plugins["graph_lint"]["thresholds"]["vulture_min_confidence"] == 80


def test_load_merges_user_overrides(tmp_path: Path):
    write(
        tmp_path / "config" / "integrity.yaml",
        """
plugins:
  graph_lint:
    thresholds:
      vulture_min_confidence: 60
""",
    )
    cfg = load_config(tmp_path)
    assert cfg.plugins["graph_lint"]["thresholds"]["vulture_min_confidence"] == 60
    assert cfg.plugins["graph_lint"]["thresholds"]["density_drop_pct"] == 25  # default kept


def test_env_override_int_threshold(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INTEGRITY_VULTURE_MIN_CONFIDENCE", "70")
    cfg = load_config(tmp_path)
    assert cfg.plugins["graph_lint"]["thresholds"]["vulture_min_confidence"] == 70


def test_env_override_float_threshold(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INTEGRITY_DENSITY_DROP_PCT", "33.5")
    cfg = load_config(tmp_path)
    assert cfg.plugins["graph_lint"]["thresholds"]["density_drop_pct"] == 33.5


def test_excluded_paths_default(tmp_path: Path):
    cfg = load_config(tmp_path)
    paths = cfg.plugins["graph_lint"]["excluded_paths"]
    assert "tests/**" in paths
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest backend/tests/integrity/test_config.py -v
```
Expected: ImportError.

- [ ] **Step 3: Add `pyyaml` to backend deps**

```bash
cd backend && uv add pyyaml && cd ..
```

(If `uv add` is unavailable, edit `backend/pyproject.toml` `dependencies = [...]` to include `"pyyaml>=6.0"` and run `uv sync`.)

- [ ] **Step 4: Implement config module**

```python
# backend/app/integrity/config.py
from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "plugins": {
        "graph_extension": {"enabled": True},
        "graph_lint": {
            "enabled": True,
            "thresholds": {
                "vulture_min_confidence": 80,
                "density_drop_pct": 25,
                "orphan_growth_pct": 20,
                "module_min_nodes": 5,
                "snapshot_retention_days": 30,
            },
            "ignored_dead_code": [],
            "excluded_paths": [
                "tests/**",
                "**/migrations/**",
                "**/__pycache__/**",
            ],
        },
    },
}

_INT_KEYS = {
    "vulture_min_confidence",
    "module_min_nodes",
    "snapshot_retention_days",
}
_FLOAT_KEYS = {
    "density_drop_pct",
    "orphan_growth_pct",
}


@dataclass(frozen=True)
class IntegrityConfig:
    plugins: dict[str, Any] = field(default_factory=dict)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coerce(key: str, raw: str) -> Any:
    if key in _INT_KEYS:
        return int(raw)
    if key in _FLOAT_KEYS:
        return float(raw)
    return raw


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = deepcopy(cfg)
    thresholds = cfg["plugins"]["graph_lint"]["thresholds"]
    for key in list(thresholds.keys()):
        env_var = f"INTEGRITY_{key.upper()}"
        if env_var in os.environ:
            thresholds[key] = _coerce(key, os.environ[env_var])
    return cfg


def load_config(repo_root: Path) -> IntegrityConfig:
    yaml_path = repo_root / "config" / "integrity.yaml"
    user: dict[str, Any] = {}
    if yaml_path.exists():
        loaded = yaml.safe_load(yaml_path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{yaml_path}: top-level must be a mapping")
        user = loaded
    merged = _deep_merge(DEFAULTS, user)
    merged = _apply_env_overrides(merged)
    return IntegrityConfig(plugins=merged["plugins"])
```

- [ ] **Step 5: Run to confirm passes**

```
uv run pytest backend/tests/integrity/test_config.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/config.py backend/tests/integrity/test_config.py backend/pyproject.toml
# include uv.lock only if it changed
git status backend/uv.lock 2>/dev/null && git add backend/uv.lock
git commit -m "feat(integrity): config loader with YAML + INTEGRITY_* env overrides"
```

---

## Task 6: Report aggregator

**Files:**
- Create: `backend/app/integrity/report.py`
- Test: `backend/tests/integrity/test_report.py`

Aggregates `ScanResult`s into one `IntegrityReport`. Writes `integrity-out/{date}/report.json`, `report.md`, then `docs/health/latest.md` (committed) and appends today's row(s) to `docs/health/trend.md` (trims to 30 days). Carries `first_seen` from previous report.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_report.py
import json
from datetime import date
from pathlib import Path

import pytest

from backend.app.integrity.issue import IntegrityIssue
from backend.app.integrity.protocol import ScanResult
from backend.app.integrity.report import write_report


def issue(rule: str = "graph.dead_code", node_id: str = "x", severity: str = "WARN") -> IntegrityIssue:
    return IntegrityIssue(
        rule=rule, severity=severity, node_id=node_id,
        location="x.py:1", message="m", evidence={}, first_seen="2026-04-17",
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_writes_report_json_and_md(repo: Path):
    results = [ScanResult(plugin_name="graph_lint", plugin_version="1.0.0", issues=[issue()])]
    paths = write_report(repo, results, today=date(2026, 4, 17))
    rj = repo / "integrity-out" / "2026-04-17" / "report.json"
    rm = repo / "integrity-out" / "2026-04-17" / "report.md"
    assert rj.exists() and rm.exists()
    data = json.loads(rj.read_text())
    assert data["date"] == "2026-04-17"
    assert data["counts"]["WARN"] == 1
    assert "graph.dead_code" in rm.read_text()
    assert paths.report_json == rj


def test_writes_docs_health_latest_md(repo: Path):
    results = [ScanResult(plugin_name="graph_lint", plugin_version="1.0.0", issues=[issue()])]
    write_report(repo, results, today=date(2026, 4, 17))
    latest = repo / "docs" / "health" / "latest.md"
    assert latest.exists()
    assert "graph_lint" in latest.read_text()


def test_appends_to_trend_md(repo: Path):
    r1 = [ScanResult(plugin_name="graph_lint", plugin_version="1.0.0", issues=[issue()])]
    write_report(repo, r1, today=date(2026, 4, 17))
    r2 = [ScanResult(
        plugin_name="graph_lint", plugin_version="1.0.0",
        issues=[issue(node_id="y"), issue(node_id="z")]
    )]
    write_report(repo, r2, today=date(2026, 4, 18))
    trend = (repo / "docs" / "health" / "trend.md").read_text()
    assert "2026-04-17" in trend and "2026-04-18" in trend
    # second day has 2 WARN
    lines = [l for l in trend.splitlines() if "2026-04-18" in l and "graph_lint" in l]
    assert any("2" in l for l in lines)


def test_trend_md_trims_to_30_days(repo: Path):
    from datetime import timedelta
    base = date(2026, 4, 17)
    for i in range(0, 35):
        write_report(
            repo,
            [ScanResult(plugin_name="graph_lint", plugin_version="1.0.0", issues=[issue()])],
            today=base - timedelta(days=i),
        )
    trend = (repo / "docs" / "health" / "trend.md").read_text()
    # Oldest row should be base - 29 days, NOT base - 34 days
    assert (base - timedelta(days=29)).isoformat() in trend
    assert (base - timedelta(days=34)).isoformat() not in trend


def test_carries_first_seen_from_previous_report(repo: Path):
    today_issue = IntegrityIssue(
        rule="graph.dead_code", severity="WARN", node_id="x",
        location="x.py:1", message="m", evidence={}, first_seen="2026-04-17",
    )
    write_report(
        repo,
        [ScanResult(plugin_name="graph_lint", plugin_version="1.0.0", issues=[today_issue])],
        today=date(2026, 4, 17),
    )
    later_issue = IntegrityIssue(
        rule="graph.dead_code", severity="WARN", node_id="x",
        location="x.py:1", message="m", evidence={}, first_seen="2026-04-20",
    )
    write_report(
        repo,
        [ScanResult(plugin_name="graph_lint", plugin_version="1.0.0", issues=[later_issue])],
        today=date(2026, 4, 20),
    )
    later_data = json.loads((repo / "integrity-out" / "2026-04-20" / "report.json").read_text())
    issue_x = next(i for i in later_data["issues"] if i["node_id"] == "x")
    assert issue_x["first_seen"] == "2026-04-17"
```

- [ ] **Step 2: Run to confirm failures**

```
uv run pytest backend/tests/integrity/test_report.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement report aggregator**

```python
# backend/app/integrity/report.py
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .issue import IntegrityIssue, carry_first_seen
from .protocol import ScanResult


@dataclass(frozen=True)
class ReportPaths:
    report_json: Path
    report_md: Path
    latest_md: Path
    trend_md: Path
    run_dir: Path


def _run_dir(repo_root: Path, today: date) -> Path:
    d = repo_root / "integrity-out" / today.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_prior_issues(repo_root: Path, today: date) -> list[IntegrityIssue]:
    """Walk integrity-out/* for the most recent report.json older than today."""
    base = repo_root / "integrity-out"
    if not base.exists():
        return []
    candidates: list[date] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        try:
            d = date.fromisoformat(child.name)
        except ValueError:
            continue
        if d < today and (child / "report.json").exists():
            candidates.append(d)
    if not candidates:
        return []
    latest = max(candidates)
    data = json.loads((base / latest.isoformat() / "report.json").read_text())
    return [IntegrityIssue.from_dict(d) for d in data.get("issues", [])]


def _render_report_md(today: date, results: list[ScanResult], counts: dict[str, int]) -> str:
    lines = [
        f"# Integrity report — {today.isoformat()}",
        "",
        "## Counts by severity",
        "",
    ]
    for sev in ("CRITICAL", "ERROR", "WARN", "INFO"):
        lines.append(f"- **{sev}**: {counts.get(sev, 0)}")
    lines.append("")
    for r in results:
        lines.append(f"## {r.plugin_name} (v{r.plugin_version})")
        lines.append("")
        if r.failures:
            lines.append("**Failures:**")
            for f in r.failures:
                lines.append(f"- {f}")
            lines.append("")
        if not r.issues:
            lines.append("_No issues._")
            lines.append("")
            continue
        lines.append("| Rule | Severity | Node | Location | Message |")
        lines.append("|------|----------|------|----------|---------|")
        for i in r.issues:
            msg = i.message.replace("|", "\\|")
            lines.append(f"| {i.rule} | {i.severity} | `{i.node_id}` | {i.location} | {msg} |")
        lines.append("")
    return "\n".join(lines)


def _render_latest_md(today: date, results: list[ScanResult], counts: dict[str, int]) -> str:
    lines = [
        f"# Health — {today.isoformat()}",
        "",
        f"_Last run: {today.isoformat()}_",
        "",
        "## Summary",
        "",
    ]
    for sev in ("ERROR", "WARN", "INFO"):
        lines.append(f"- **{sev}**: {counts.get(sev, 0)}")
    lines.append("")
    for r in results:
        lines.append(f"## {r.plugin_name}")
        lines.append("")
        per_rule: dict[str, int] = Counter(i.rule for i in r.issues)
        if not per_rule:
            lines.append("_Clean._")
        else:
            for rule, n in sorted(per_rule.items()):
                lines.append(f"- `{rule}`: {n}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"Full report: `integrity-out/{today.isoformat()}/report.md`")
    return "\n".join(lines)


def _append_trend(trend_path: Path, today: date, results: list[ScanResult], retention_days: int) -> None:
    header = "| date | plugin | severity | count |"
    sep = "|------|--------|----------|-------|"
    rows: list[str] = []
    if trend_path.exists():
        for line in trend_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("|--") or line.startswith("| date"):
                continue
            rows.append(line)
    cutoff = today - timedelta(days=retention_days - 1)
    kept: list[str] = []
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if not cells:
            continue
        try:
            row_date = date.fromisoformat(cells[0])
        except ValueError:
            continue
        if row_date >= cutoff:
            kept.append(row)
    today_iso = today.isoformat()
    kept = [r for r in kept if not r.startswith(f"| {today_iso} ")]
    by_plugin_sev: dict[tuple[str, str], int] = defaultdict(int)
    for r in results:
        for i in r.issues:
            by_plugin_sev[(r.plugin_name, i.severity)] += 1
    new_rows = [
        f"| {today_iso} | {plugin} | {sev} | {count} |"
        for (plugin, sev), count in sorted(by_plugin_sev.items())
    ]
    trend_path.parent.mkdir(parents=True, exist_ok=True)
    trend_path.write_text("\n".join([header, sep, *kept, *new_rows]) + "\n")


def write_report(
    repo_root: Path, results: list[ScanResult], today: date, retention_days: int = 30
) -> ReportPaths:
    prior = _load_prior_issues(repo_root, today)
    final_results: list[ScanResult] = []
    all_issues_today: list[IntegrityIssue] = []
    for r in results:
        carried = carry_first_seen(list(r.issues), prior)
        all_issues_today.extend(carried)
        final_results.append(
            ScanResult(
                plugin_name=r.plugin_name,
                plugin_version=r.plugin_version,
                issues=carried,
                artifacts=list(r.artifacts),
                failures=list(r.failures),
            )
        )

    counts: dict[str, int] = Counter(i.severity for i in all_issues_today)
    run_dir = _run_dir(repo_root, today)

    payload: dict[str, Any] = {
        "date": today.isoformat(),
        "counts": dict(counts),
        "plugins": [
            {
                "name": r.plugin_name,
                "version": r.plugin_version,
                "failures": r.failures,
                "issue_count": len(r.issues),
            }
            for r in final_results
        ],
        "issues": [i.to_dict() for i in all_issues_today],
    }
    report_json = run_dir / "report.json"
    report_json.write_text(json.dumps(payload, indent=2, sort_keys=True))

    report_md = run_dir / "report.md"
    report_md.write_text(_render_report_md(today, final_results, counts))

    latest_md = repo_root / "docs" / "health" / "latest.md"
    latest_md.parent.mkdir(parents=True, exist_ok=True)
    latest_md.write_text(_render_latest_md(today, final_results, counts))

    trend_md = repo_root / "docs" / "health" / "trend.md"
    _append_trend(trend_md, today, final_results, retention_days)

    latest_link = repo_root / "integrity-out" / "latest"
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(today.isoformat(), target_is_directory=True)

    return ReportPaths(
        report_json=report_json,
        report_md=report_md,
        latest_md=latest_md,
        trend_md=trend_md,
        run_dir=run_dir,
    )
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/test_report.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/report.py backend/tests/integrity/test_report.py
git commit -m "feat(integrity): report aggregator writes report+latest+trend with first_seen carry"
```

---

## Task 7: Module CLI `python -m backend.app.integrity`

**Files:**
- Create: `backend/app/integrity/__main__.py`
- Test: `backend/tests/integrity/test_main_cli.py`

Argparse-based CLI. Wires together engine + plugins + report + snapshot. Flags: `--plugin <name>` (run only one), `--no-augment` (skip Plugin A's regen), `--retention-days N`. Exits non-zero only on engine-level failure (per spec §10), not on plugin issues.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_main_cli.py
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "graphify").mkdir()
    (tmp_path / "graphify" / "graph.json").write_text(
        json.dumps({"nodes": [], "links": []})
    )
    return tmp_path


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "backend.app.integrity", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent.parent)},
    )


def test_cli_runs_and_writes_report(repo: Path):
    result = run_cli(repo, "--no-augment")
    assert result.returncode == 0, result.stderr
    today_dirs = list((repo / "integrity-out").glob("*"))
    assert any((d / "report.json").exists() for d in today_dirs if d.is_dir())


def test_cli_plugin_filter_runs_only_named(repo: Path):
    result = run_cli(repo, "--no-augment", "--plugin", "graph_lint")
    assert result.returncode == 0, result.stderr


def test_cli_unknown_plugin_exits_nonzero(repo: Path):
    result = run_cli(repo, "--plugin", "nonexistent")
    assert result.returncode != 0
    assert "nonexistent" in result.stderr
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest backend/tests/integrity/test_main_cli.py -v
```
Expected: failure (no `__main__.py` yet, or test_cli_unknown_plugin_exits_nonzero passes accidentally).

- [ ] **Step 3: Implement `__main__.py`**

```python
# backend/app/integrity/__main__.py
"""Integrity engine CLI: python -m backend.app.integrity."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .config import load_config
from .engine import IntegrityEngine
from .report import write_report
from .schema import GraphSnapshot
from .snapshots import prune_older_than, write_snapshot

KNOWN_PLUGINS = ("graph_extension", "graph_lint")


def _build_engine(repo_root: Path, only: str | None, skip_augment: bool) -> IntegrityEngine:
    cfg = load_config(repo_root)
    engine = IntegrityEngine(repo_root)
    enabled = cfg.plugins
    if only and only not in KNOWN_PLUGINS:
        raise SystemExit(f"unknown plugin: {only!r} (known: {', '.join(KNOWN_PLUGINS)})")

    if (only is None or only == "graph_extension") and not skip_augment:
        if enabled.get("graph_extension", {}).get("enabled", True):
            from .plugins.graph_extension.plugin import GraphExtensionPlugin
            engine.register(GraphExtensionPlugin())

    if only is None or only == "graph_lint":
        if enabled.get("graph_lint", {}).get("enabled", True):
            from .plugins.graph_lint.plugin import GraphLintPlugin
            engine.register(GraphLintPlugin(config=enabled.get("graph_lint", {})))

    return engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.integrity")
    parser.add_argument("--plugin", default=None, help="Run only the named plugin")
    parser.add_argument("--no-augment", action="store_true", help="Skip Plugin A's graph augmentation")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    today = date.today()

    engine = _build_engine(repo_root, args.plugin, args.no_augment)
    results = engine.run()

    report_paths = write_report(repo_root, results, today=today, retention_days=args.retention_days)

    # snapshot the merged graph for tomorrow's diffs
    merged = GraphSnapshot.load(repo_root)
    write_snapshot(repo_root, {"nodes": merged.nodes, "links": merged.links}, today=today)
    prune_older_than(repo_root, days=args.retention_days, today=today)

    print(f"Wrote {report_paths.report_md.relative_to(repo_root)}", file=sys.stderr)
    print(f"Wrote {report_paths.latest_md.relative_to(repo_root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: this CLI references `GraphLintPlugin` from `backend/app/integrity/plugins/graph_lint/plugin.py`. The test will only pass once Task 8 lands. To keep TDD honest:

- [ ] **Step 4: Stub `GraphLintPlugin` so CLI tests can import**

Create the file with a no-op scan so Task 7 tests pass; Task 8 fleshes it out.

```python
# backend/app/integrity/plugins/graph_lint/__init__.py
```

```python
# backend/app/integrity/plugins/graph_lint/plugin.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...protocol import ScanContext, ScanResult


@dataclass
class GraphLintPlugin:
    name: str = "graph_lint"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("graph_extension",)
    paths: tuple[str, ...] = (
        "backend/app/**/*.py",
        "frontend/src/**/*.{ts,tsx,js,jsx}",
        "graphify/graph.json",
        "graphify/graph.augmented.json",
    )
    config: dict[str, Any] = field(default_factory=dict)

    def scan(self, ctx: ScanContext) -> ScanResult:
        return ScanResult(plugin_name=self.name, plugin_version=self.version)
```

- [ ] **Step 5: Run to confirm CLI tests pass**

```
uv run pytest backend/tests/integrity/test_main_cli.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/__main__.py \
        backend/app/integrity/plugins/graph_lint/__init__.py \
        backend/app/integrity/plugins/graph_lint/plugin.py \
        backend/tests/integrity/test_main_cli.py
git commit -m "feat(integrity): module CLI dispatches engine with plugin filter + snapshot rotation"
```

---

## Task 8: Plugin B shell + scan shell

**Files:**
- Modify: `backend/app/integrity/plugins/graph_lint/plugin.py`
- Create: `backend/app/integrity/plugins/graph_lint/__main__.py`
- Test: `backend/tests/integrity/plugins/graph_lint/test_plugin.py`

Flesh out `scan()` to return rule outputs in a deterministic order. Each rule is a `Callable[[ScanContext, dict], list[IntegrityIssue]]`. Plugin orchestrates and writes `integrity-out/{today}/graph_lint.json`. Standalone `__main__` mirrors A's pattern.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/test_plugin.py
import json
from datetime import date
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_lint.plugin import GraphLintPlugin
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "graphify").mkdir()
    (tmp_path / "graphify" / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))
    return tmp_path


def test_plugin_returns_scan_result(repo: Path):
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))
    plugin = GraphLintPlugin(today=date(2026, 4, 17))
    result = plugin.scan(ctx)
    assert result.plugin_name == "graph_lint"
    assert isinstance(result.issues, list)


def test_plugin_writes_artifact(repo: Path):
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))
    plugin = GraphLintPlugin(today=date(2026, 4, 17))
    result = plugin.scan(ctx)
    artifact = repo / "integrity-out" / "2026-04-17" / "graph_lint.json"
    assert artifact.exists()
    assert artifact in result.artifacts
    data = json.loads(artifact.read_text())
    assert "issues" in data and "rules_run" in data


def test_plugin_skips_disabled_rules(repo: Path):
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))
    plugin = GraphLintPlugin(
        today=date(2026, 4, 17),
        config={"thresholds": {}, "ignored_dead_code": [], "excluded_paths": [],
                "disabled_rules": ["graph.dead_code"]},
    )
    result = plugin.scan(ctx)
    artifact_data = json.loads(
        (repo / "integrity-out" / "2026-04-17" / "graph_lint.json").read_text()
    )
    assert "graph.dead_code" not in artifact_data["rules_run"]
```

- [ ] **Step 2: Run to confirm failures**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/test_plugin.py -v
```
Expected: AttributeError (no `today` arg, no artifact write yet).

- [ ] **Step 3: Implement plugin shell**

```python
# backend/app/integrity/plugins/graph_lint/plugin.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from ...issue import IntegrityIssue
from ...protocol import ScanContext, ScanResult

# Rule signature: ctx, plugin_config, today -> list[IntegrityIssue]
Rule = Callable[[ScanContext, dict[str, Any], date], list[IntegrityIssue]]


def _default_rules() -> dict[str, Rule]:
    # Imported lazily so subagents can build the plugin shell before all rules exist.
    from .rules import dead_code, density_drop, drift, handler_unbound, orphan_growth
    return {
        "graph.dead_code": dead_code.run,
        "graph.drift_added": drift.run_added,
        "graph.drift_removed": drift.run_removed,
        "graph.density_drop": density_drop.run,
        "graph.orphan_growth": orphan_growth.run,
        "graph.handler_unbound": handler_unbound.run,
    }


@dataclass
class GraphLintPlugin:
    name: str = "graph_lint"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("graph_extension",)
    paths: tuple[str, ...] = (
        "backend/app/**/*.py",
        "frontend/src/**/*.{ts,tsx,js,jsx}",
        "graphify/graph.json",
        "graphify/graph.augmented.json",
    )
    config: dict[str, Any] = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    rules: dict[str, Rule] | None = None

    def scan(self, ctx: ScanContext) -> ScanResult:
        rules = self.rules if self.rules is not None else _default_rules()
        disabled = set(self.config.get("disabled_rules", []))

        all_issues: list[IntegrityIssue] = []
        rules_run: list[str] = []
        failures: list[str] = []

        for rule_id, fn in rules.items():
            if rule_id in disabled:
                continue
            try:
                issues = fn(ctx, self.config, self.today)
                all_issues.extend(issues)
                rules_run.append(rule_id)
            except Exception as exc:
                failures.append(f"{rule_id}: {type(exc).__name__}: {exc}")
                all_issues.append(
                    IntegrityIssue(
                        rule=rule_id,
                        severity="ERROR",
                        node_id="<rule-failure>",
                        location=f"graph_lint/{rule_id}",
                        message=f"{type(exc).__name__}: {exc}",
                    )
                )

        run_dir = ctx.repo_root / "integrity-out" / self.today.isoformat()
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact = run_dir / "graph_lint.json"
        artifact.write_text(
            json.dumps(
                {
                    "date": self.today.isoformat(),
                    "rules_run": rules_run,
                    "failures": failures,
                    "issues": [i.to_dict() for i in all_issues],
                },
                indent=2,
                sort_keys=True,
            )
        )

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            issues=all_issues,
            artifacts=[artifact],
            failures=failures,
        )
```

- [ ] **Step 4: Stub rule modules so import doesn't blow up**

Create empty rule shells that return `[]`. Tasks 12–16 implement them properly.

```python
# backend/app/integrity/plugins/graph_lint/rules/__init__.py
```

```python
# backend/app/integrity/plugins/graph_lint/rules/dead_code.py
from __future__ import annotations
from datetime import date
from typing import Any
from ....issue import IntegrityIssue
from ....protocol import ScanContext


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    return []
```

(Same shape, different module name, for `drift.py` with `run_added`+`run_removed`, and for `density_drop.py`, `orphan_growth.py`, `handler_unbound.py` each with `run`.)

```python
# backend/app/integrity/plugins/graph_lint/rules/drift.py
from __future__ import annotations
from datetime import date
from typing import Any
from ....issue import IntegrityIssue
from ....protocol import ScanContext


def run_added(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    return []


def run_removed(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    return []
```

```python
# backend/app/integrity/plugins/graph_lint/rules/density_drop.py
from __future__ import annotations
from datetime import date
from typing import Any
from ....issue import IntegrityIssue
from ....protocol import ScanContext


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    return []
```

```python
# backend/app/integrity/plugins/graph_lint/rules/orphan_growth.py
from __future__ import annotations
from datetime import date
from typing import Any
from ....issue import IntegrityIssue
from ....protocol import ScanContext


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    return []
```

```python
# backend/app/integrity/plugins/graph_lint/rules/handler_unbound.py
from __future__ import annotations
from datetime import date
from typing import Any
from ....issue import IntegrityIssue
from ....protocol import ScanContext


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    return []
```

- [ ] **Step 5: Implement standalone CLI `__main__.py`**

```python
# backend/app/integrity/plugins/graph_lint/__main__.py
"""Standalone CLI: python -m backend.app.integrity.plugins.graph_lint."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from ...config import load_config
from ...protocol import ScanContext
from ...schema import GraphSnapshot
from .plugin import GraphLintPlugin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.integrity.plugins.graph_lint")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    cfg = load_config(repo_root)
    plugin = GraphLintPlugin(config=cfg.plugins.get("graph_lint", {}), today=date.today())
    ctx = ScanContext(repo_root=repo_root, graph=GraphSnapshot.load(repo_root))
    result = plugin.scan(ctx)
    print(f"graph_lint: {len(result.issues)} issues, {len(result.failures)} failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the test**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/test_plugin.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Add `__init__.py` for the new test dir**

```bash
mkdir -p backend/tests/integrity/plugins/graph_lint/rules
mkdir -p backend/tests/integrity/plugins/graph_lint/wrappers
touch backend/tests/integrity/plugins/graph_lint/__init__.py
touch backend/tests/integrity/plugins/graph_lint/rules/__init__.py
touch backend/tests/integrity/plugins/graph_lint/wrappers/__init__.py
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/ \
        backend/tests/integrity/plugins/graph_lint/__init__.py \
        backend/tests/integrity/plugins/graph_lint/rules/__init__.py \
        backend/tests/integrity/plugins/graph_lint/wrappers/__init__.py \
        backend/tests/integrity/plugins/graph_lint/test_plugin.py
git commit -m "feat(integrity): GraphLintPlugin shell with rule registry + per-rule failure isolation"
```

---

## Task 9: Orphan helper

**Files:**
- Create: `backend/app/integrity/plugins/graph_lint/orphans.py`
- Test: `backend/tests/integrity/plugins/graph_lint/test_orphans.py`

Reuses the orphan-definition logic from `scripts/verify_orphans.py` (post-rewrite) but operates on a `GraphSnapshot` directly. Returns list of orphan node IDs (no inbound EXTRACTED edges in `USE_RELATIONS`, code file_type, not test/entry/migration).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/test_orphans.py
from backend.app.integrity.plugins.graph_lint.orphans import find_orphans
from backend.app.integrity.schema import GraphSnapshot


def make(nodes, links):
    return GraphSnapshot(nodes=nodes, links=links)


def test_returns_node_with_no_inbound_extracted():
    g = make(
        nodes=[
            {"id": "a", "label": "a", "file_type": "code", "source_file": "backend/app/x.py"},
            {"id": "b", "label": "b", "file_type": "code", "source_file": "backend/app/y.py"},
        ],
        links=[],
    )
    assert find_orphans(g) == ["a", "b"]


def test_excludes_nodes_with_inbound_extracted():
    g = make(
        nodes=[
            {"id": "a", "label": "a", "file_type": "code", "source_file": "backend/app/x.py"},
            {"id": "b", "label": "b", "file_type": "code", "source_file": "backend/app/y.py"},
        ],
        links=[
            {"source": "a", "target": "b", "relation": "calls", "confidence": "EXTRACTED"},
        ],
    )
    assert find_orphans(g) == ["a"]


def test_ignores_inferred_edges():
    g = make(
        nodes=[
            {"id": "a", "label": "a", "file_type": "code", "source_file": "backend/app/x.py"},
            {"id": "b", "label": "b", "file_type": "code", "source_file": "backend/app/y.py"},
        ],
        links=[
            {"source": "a", "target": "b", "relation": "calls", "confidence": "INFERRED"},
        ],
    )
    assert "b" in find_orphans(g)


def test_excludes_test_files_and_entry_points():
    g = make(
        nodes=[
            {"id": "main_app", "label": "main", "file_type": "code", "source_file": "backend/app/main.py"},
            {"id": "x_test_a", "label": "test_a", "file_type": "code", "source_file": "backend/tests/x_test.py"},
            {"id": "init_x", "label": "x", "file_type": "code", "source_file": "backend/app/x/__init__.py"},
        ],
        links=[],
    )
    assert find_orphans(g) == []


def test_excludes_non_code_file_types():
    g = make(
        nodes=[
            {"id": "doc", "label": "doc", "file_type": "document", "source_file": "docs/x.md"},
        ],
        links=[],
    )
    assert find_orphans(g) == []
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/test_orphans.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement orphan helper**

```python
# backend/app/integrity/plugins/graph_lint/orphans.py
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

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
    if src.endswith((".md", ".json", ".yaml", ".yml", ".html", ".css", ".svg")):
        return True
    return False


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
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/test_orphans.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/orphans.py \
        backend/tests/integrity/plugins/graph_lint/test_orphans.py
git commit -m "feat(integrity): orphan helper for graph_lint dead_code rule"
```

---

## Task 10: Vulture wrapper

**Files:**
- Create: `backend/app/integrity/plugins/graph_lint/wrappers/__init__.py`
- Create: `backend/app/integrity/plugins/graph_lint/wrappers/vulture.py`
- Test: `backend/tests/integrity/plugins/graph_lint/wrappers/test_vulture.py`

Subprocess wrapper. Captures vulture output as a list of `VultureFinding(name, location, kind, confidence)`. Errors are returned as a `failure_message` instead of raising.

NOTE: vulture's actual output is `path:line: <kind> '<name>' (NN% confidence)`. There is no JSON output mode in vulture (verify with the live tool). Parse the text.

- [ ] **Step 1: Write the failing test (using a stub binary)**

```python
# backend/tests/integrity/plugins/graph_lint/wrappers/test_vulture.py
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_lint.wrappers.vulture import (
    VultureFinding,
    parse_vulture_output,
    run_vulture,
)


SAMPLE_OUTPUT = """\
backend/app/x.py:10: unused function 'old_helper' (90% confidence)
backend/app/y.py:42: unused variable '_unused' (60% confidence)
"""


def test_parse_extracts_findings():
    findings = parse_vulture_output(SAMPLE_OUTPUT)
    assert len(findings) == 2
    assert findings[0] == VultureFinding(
        path="backend/app/x.py", line=10, kind="function", name="old_helper", confidence=90
    )
    assert findings[1].confidence == 60


def test_parse_skips_garbage_lines():
    out = "Hello there\nbackend/app/x.py:10: unused function 'old' (90% confidence)\n"
    findings = parse_vulture_output(out)
    assert len(findings) == 1


def test_run_vulture_handles_missing_binary(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    result = run_vulture(tmp_path / "app", min_confidence=80, vulture_bin="definitely_not_a_binary")
    assert result.findings == []
    assert "definitely_not_a_binary" in result.failure_message


def test_run_vulture_executes_real_binary(tmp_path: Path):
    # Write a tiny module with one obvious unused
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def used():\n    return 1\n\n"
        "def _unused_priv():\n    return 2\n\n"
        "used()\n"
    )
    try:
        subprocess.run(["vulture", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("vulture not installed")
    result = run_vulture(pkg, min_confidence=60)
    assert result.failure_message == ""
    names = {f.name for f in result.findings}
    assert "_unused_priv" in names or any("unused" in f.name for f in result.findings)
```

- [ ] **Step 2: Run to confirm failures**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/wrappers/test_vulture.py -v
```
Expected: ImportError.

- [ ] **Step 3: Add vulture to backend deps**

```bash
cd backend && uv add --dev vulture && cd ..
```

(If `uv add` is unavailable, edit `backend/pyproject.toml` to include vulture under `[project.optional-dependencies] dev = [...]` or `[tool.uv.dev-dependencies]` and run `uv sync`.)

- [ ] **Step 4: Implement vulture wrapper**

```python
# backend/app/integrity/plugins/graph_lint/wrappers/__init__.py
```

```python
# backend/app/integrity/plugins/graph_lint/wrappers/vulture.py
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):\s*unused\s+(?P<kind>\w+)\s+'(?P<name>[^']+)'\s+\((?P<conf>\d+)%\s+confidence\)"
)


@dataclass(frozen=True)
class VultureFinding:
    path: str
    line: int
    kind: str
    name: str
    confidence: int


@dataclass(frozen=True)
class VultureResult:
    findings: list[VultureFinding] = field(default_factory=list)
    failure_message: str = ""


def parse_vulture_output(text: str) -> list[VultureFinding]:
    out: list[VultureFinding] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        out.append(
            VultureFinding(
                path=m.group("path"),
                line=int(m.group("line")),
                kind=m.group("kind"),
                name=m.group("name"),
                confidence=int(m.group("conf")),
            )
        )
    return out


def run_vulture(target: Path, *, min_confidence: int, vulture_bin: str = "vulture") -> VultureResult:
    cmd = [vulture_bin, str(target), "--min-confidence", str(min_confidence)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    except FileNotFoundError as exc:
        return VultureResult(failure_message=f"vulture binary not found: {vulture_bin} ({exc})")
    except subprocess.TimeoutExpired:
        return VultureResult(failure_message="vulture timed out after 120s")

    # vulture exits 0 if no findings, 3 if findings present. Other codes = error.
    if proc.returncode not in (0, 3):
        return VultureResult(failure_message=f"vulture exited {proc.returncode}: {proc.stderr.strip()}")

    return VultureResult(findings=parse_vulture_output(proc.stdout))
```

- [ ] **Step 5: Run to confirm passes**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/wrappers/test_vulture.py -v
```
Expected: 4 passed (or 3 passed + 1 skipped if vulture install hasn't completed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/wrappers/__init__.py \
        backend/app/integrity/plugins/graph_lint/wrappers/vulture.py \
        backend/tests/integrity/plugins/graph_lint/wrappers/test_vulture.py \
        backend/pyproject.toml
git status backend/uv.lock 2>/dev/null && git add backend/uv.lock
git commit -m "feat(integrity): vulture wrapper with text-output parser + error capture"
```

---

## Task 11: Knip wrapper

**Files:**
- Create: `backend/app/integrity/plugins/graph_lint/wrappers/knip.py`
- Test: `backend/tests/integrity/plugins/graph_lint/wrappers/test_knip.py`
- Modify: `frontend/package.json`
- Create: `frontend/knip.json`

Subprocess wrapper around `npx knip --reporter json`. Knip emits structured JSON. Captures `files` (unused files), `exports` (unused exports per file), `dependencies` (unused deps).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/wrappers/test_knip.py
import json
import subprocess
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_lint.wrappers.knip import (
    KnipFinding,
    parse_knip_output,
    run_knip,
)


SAMPLE = json.dumps({
    "files": ["frontend/src/dead/orphan.tsx"],
    "issues": [
        {
            "file": "frontend/src/api.ts",
            "exports": [{"name": "unusedExport", "line": 12, "col": 1}],
        }
    ],
})


def test_parse_extracts_unused_files():
    findings = parse_knip_output(SAMPLE)
    files = [f for f in findings if f.kind == "file"]
    assert len(files) == 1
    assert files[0].path == "frontend/src/dead/orphan.tsx"


def test_parse_extracts_unused_exports():
    findings = parse_knip_output(SAMPLE)
    exports = [f for f in findings if f.kind == "export"]
    assert len(exports) == 1
    assert exports[0].name == "unusedExport"
    assert exports[0].path == "frontend/src/api.ts"
    assert exports[0].line == 12


def test_parse_handles_empty_input():
    assert parse_knip_output("{}") == []
    assert parse_knip_output("") == []


def test_run_knip_handles_missing_binary(tmp_path: Path, monkeypatch):
    result = run_knip(tmp_path, knip_bin="definitely_not_a_binary")
    assert result.findings == []
    assert "definitely_not_a_binary" in result.failure_message
```

- [ ] **Step 2: Run to confirm failures**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/wrappers/test_knip.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement knip wrapper**

```python
# backend/app/integrity/plugins/graph_lint/wrappers/knip.py
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

KnipKind = Literal["file", "export", "dependency"]


@dataclass(frozen=True)
class KnipFinding:
    kind: KnipKind
    path: str
    name: str = ""
    line: int = 0


@dataclass(frozen=True)
class KnipResult:
    findings: list[KnipFinding] = field(default_factory=list)
    failure_message: str = ""


def parse_knip_output(text: str) -> list[KnipFinding]:
    if not text.strip():
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    out: list[KnipFinding] = []
    for path in data.get("files", []) or []:
        out.append(KnipFinding(kind="file", path=path))
    for issue in data.get("issues", []) or []:
        path = issue.get("file", "")
        for exp in issue.get("exports", []) or []:
            out.append(
                KnipFinding(
                    kind="export",
                    path=path,
                    name=exp.get("name", ""),
                    line=int(exp.get("line", 0) or 0),
                )
            )
        for dep in issue.get("dependencies", []) or []:
            out.append(KnipFinding(kind="dependency", path=path, name=dep.get("name", "")))
    return out


def run_knip(frontend_dir: Path, *, knip_bin: str = "npx") -> KnipResult:
    cmd = [knip_bin, "knip", "--reporter", "json"] if knip_bin == "npx" else [knip_bin, "--reporter", "json"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=180,
            cwd=str(frontend_dir),
        )
    except FileNotFoundError as exc:
        return KnipResult(failure_message=f"knip binary not found: {knip_bin} ({exc})")
    except subprocess.TimeoutExpired:
        return KnipResult(failure_message="knip timed out after 180s")

    # knip exits 1 when issues are found — same shape as a successful scan with findings.
    if proc.returncode not in (0, 1):
        return KnipResult(failure_message=f"knip exited {proc.returncode}: {proc.stderr.strip()[:500]}")

    return KnipResult(findings=parse_knip_output(proc.stdout))
```

- [ ] **Step 4: Add knip to frontend dev deps + create config**

```bash
cd frontend && npm install --save-dev knip && cd ..
```

```json
// frontend/knip.json
{
  "$schema": "https://unpkg.com/knip@5/schema.json",
  "entry": [
    "src/main.tsx",
    "src/App.tsx",
    "vite.config.ts",
    "playwright.config.ts"
  ],
  "project": ["src/**/*.{ts,tsx}"],
  "ignore": [
    "src/**/__tests__/**",
    "src/**/*.test.{ts,tsx}",
    "e2e/**"
  ],
  "ignoreDependencies": []
}
```

- [ ] **Step 5: Run wrapper test**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/wrappers/test_knip.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Smoke-test knip locally**

```
cd frontend && npx knip --reporter json | head -40 && cd ..
```
Expected: JSON output (may include current real findings — fine).

- [ ] **Step 7: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/wrappers/knip.py \
        backend/tests/integrity/plugins/graph_lint/wrappers/test_knip.py \
        frontend/package.json frontend/knip.json
git status frontend/package-lock.json 2>/dev/null && git add frontend/package-lock.json
git commit -m "feat(integrity): knip wrapper + frontend knip config"
```

---

## Task 12: Rule — `graph.dead_code` (triple-intersection)

**Files:**
- Modify: `backend/app/integrity/plugins/graph_lint/rules/dead_code.py`
- Test: `backend/tests/integrity/plugins/graph_lint/rules/test_dead_code.py`

Match logic:
- A Python orphan (`<filestem>_<symbol>`) is dead-code-confirmed iff vulture also flagged that `(path, symbol)`.
- A frontend orphan is confirmed iff knip flagged the file (`KnipFinding.kind == "file"`) OR a matching export.
- Skip if `node_id` in `config.ignored_dead_code` or location matches `# noqa: dead-code` / `// knip-ignore` line comment in source.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/rules/test_dead_code.py
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.integrity.plugins.graph_lint.rules import dead_code
from backend.app.integrity.plugins.graph_lint.wrappers.knip import KnipFinding, KnipResult
from backend.app.integrity.plugins.graph_lint.wrappers.vulture import VultureFinding, VultureResult
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    return tmp_path


def make_ctx(repo: Path, nodes: list[dict], links: list[dict]) -> ScanContext:
    return ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=links))


def test_python_orphan_confirmed_by_vulture(repo: Path):
    (repo / "backend" / "app" / "x.py").write_text("def old_helper():\n    pass\n")
    nodes = [
        {"id": "x_old_helper", "label": "old_helper", "file_type": "code",
         "source_file": "backend/app/x.py", "kind": "function"},
    ]
    ctx = make_ctx(repo, nodes, [])
    with patch.object(dead_code, "_run_vulture") as mv, patch.object(dead_code, "_run_knip") as mk:
        mv.return_value = VultureResult(findings=[
            VultureFinding(path="backend/app/x.py", line=1, kind="function", name="old_helper", confidence=90)
        ])
        mk.return_value = KnipResult()
        issues = dead_code.run(ctx, {"thresholds": {"vulture_min_confidence": 80}}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.dead_code"
    assert issues[0].evidence == {"vulture": True, "knip": False, "graph_orphan": True}


def test_frontend_orphan_confirmed_by_knip_file(repo: Path):
    nodes = [
        {"id": "orphan_default", "label": "default", "file_type": "code",
         "source_file": "frontend/src/dead/orphan.tsx", "kind": "function"},
    ]
    ctx = make_ctx(repo, nodes, [])
    with patch.object(dead_code, "_run_vulture") as mv, patch.object(dead_code, "_run_knip") as mk:
        mv.return_value = VultureResult()
        mk.return_value = KnipResult(findings=[
            KnipFinding(kind="file", path="frontend/src/dead/orphan.tsx")
        ])
        issues = dead_code.run(ctx, {"thresholds": {"vulture_min_confidence": 80}}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].evidence == {"vulture": False, "knip": True, "graph_orphan": True}


def test_orphan_not_in_vulture_or_knip_skipped(repo: Path):
    (repo / "backend" / "app" / "x.py").write_text("def maybe_used():\n    pass\n")
    nodes = [
        {"id": "x_maybe_used", "label": "maybe_used", "file_type": "code",
         "source_file": "backend/app/x.py", "kind": "function"},
    ]
    ctx = make_ctx(repo, nodes, [])
    with patch.object(dead_code, "_run_vulture") as mv, patch.object(dead_code, "_run_knip") as mk:
        mv.return_value = VultureResult()
        mk.return_value = KnipResult()
        issues = dead_code.run(ctx, {"thresholds": {"vulture_min_confidence": 80}}, date(2026, 4, 17))
    assert issues == []


def test_ignored_node_id_skipped(repo: Path):
    (repo / "backend" / "app" / "x.py").write_text("def old():\n    pass\n")
    nodes = [
        {"id": "x_old", "label": "old", "file_type": "code",
         "source_file": "backend/app/x.py", "kind": "function"},
    ]
    ctx = make_ctx(repo, nodes, [])
    with patch.object(dead_code, "_run_vulture") as mv, patch.object(dead_code, "_run_knip") as mk:
        mv.return_value = VultureResult(findings=[
            VultureFinding(path="backend/app/x.py", line=1, kind="function", name="old", confidence=90)
        ])
        mk.return_value = KnipResult()
        issues = dead_code.run(
            ctx,
            {"thresholds": {"vulture_min_confidence": 80}, "ignored_dead_code": ["x_old"]},
            date(2026, 4, 17),
        )
    assert issues == []


def test_noqa_comment_at_definition_line_skipped(repo: Path):
    src = (repo / "backend" / "app" / "x.py")
    src.write_text("def old():  # noqa: dead-code\n    pass\n")
    nodes = [
        {"id": "x_old", "label": "old", "file_type": "code",
         "source_file": "backend/app/x.py", "kind": "function"},
    ]
    ctx = make_ctx(repo, nodes, [])
    with patch.object(dead_code, "_run_vulture") as mv, patch.object(dead_code, "_run_knip") as mk:
        mv.return_value = VultureResult(findings=[
            VultureFinding(path="backend/app/x.py", line=1, kind="function", name="old", confidence=90)
        ])
        mk.return_value = KnipResult()
        issues = dead_code.run(ctx, {"thresholds": {"vulture_min_confidence": 80}}, date(2026, 4, 17))
    assert issues == []


def test_vulture_failure_does_not_emit_python_dead_code(repo: Path):
    nodes = [
        {"id": "x_old", "label": "old", "file_type": "code",
         "source_file": "backend/app/x.py", "kind": "function"},
    ]
    ctx = make_ctx(repo, nodes, [])
    with patch.object(dead_code, "_run_vulture") as mv, patch.object(dead_code, "_run_knip") as mk:
        mv.return_value = VultureResult(failure_message="vulture broke")
        mk.return_value = KnipResult()
        issues = dead_code.run(ctx, {"thresholds": {"vulture_min_confidence": 80}}, date(2026, 4, 17))
    assert issues == []
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_dead_code.py -v
```
Expected: failures (current run() returns []).

- [ ] **Step 3: Implement dead_code rule**

```python
# backend/app/integrity/plugins/graph_lint/rules/dead_code.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ..orphans import find_orphans
from ..wrappers.knip import KnipResult, run_knip
from ..wrappers.vulture import VultureResult, run_vulture

# Thin indirections so tests can patch.
def _run_vulture(target: Path, min_confidence: int) -> VultureResult:
    return run_vulture(target, min_confidence=min_confidence)


def _run_knip(frontend_dir: Path) -> KnipResult:
    return run_knip(frontend_dir)


_NOQA_MARKERS = ("# noqa: dead-code", "// knip-ignore")


def _has_noqa(repo_root: Path, source_file: str, line: int) -> bool:
    p = repo_root / source_file
    if not p.exists():
        return False
    try:
        src = p.read_text().splitlines()
    except OSError:
        return False
    if line < 1 or line > len(src):
        return False
    return any(marker in src[line - 1] for marker in _NOQA_MARKERS)


def _python_dead_code(
    ctx: ScanContext,
    orphans: set[str],
    vulture_result: VultureResult,
    ignored: set[str],
) -> list[IntegrityIssue]:
    if vulture_result.failure_message or not vulture_result.findings:
        return []
    nodes_by_path_and_name: dict[tuple[str, str], dict[str, Any]] = {}
    for n in ctx.graph.nodes:
        src = n.get("source_file", "") or ""
        if not src.endswith(".py"):
            continue
        nodes_by_path_and_name[(src, n.get("label", ""))] = n

    out: list[IntegrityIssue] = []
    for v in vulture_result.findings:
        node = nodes_by_path_and_name.get((v.path, v.name))
        if node is None:
            continue
        if node["id"] not in orphans:
            continue
        if node["id"] in ignored:
            continue
        if _has_noqa(ctx.repo_root, v.path, v.line):
            continue
        out.append(
            IntegrityIssue(
                rule="graph.dead_code",
                severity="WARN",
                node_id=node["id"],
                location=f"{v.path}:{v.line}",
                message="Symbol unreferenced (vulture+graph triple-confirm)",
                evidence={"vulture": True, "knip": False, "graph_orphan": True},
                fix_class="delete_dead_code",
            )
        )
    return out


def _frontend_dead_code(
    ctx: ScanContext,
    orphans: set[str],
    knip_result: KnipResult,
    ignored: set[str],
) -> list[IntegrityIssue]:
    if knip_result.failure_message or not knip_result.findings:
        return []
    files_flagged: set[str] = {f.path for f in knip_result.findings if f.kind == "file"}
    exports_flagged: dict[str, set[str]] = {}
    for f in knip_result.findings:
        if f.kind == "export":
            exports_flagged.setdefault(f.path, set()).add(f.name)

    out: list[IntegrityIssue] = []
    for n in ctx.graph.nodes:
        src = n.get("source_file", "") or ""
        if not src.endswith((".ts", ".tsx", ".js", ".jsx")):
            continue
        if n["id"] not in orphans:
            continue
        if n["id"] in ignored:
            continue
        knip_match = src in files_flagged or n.get("label", "") in exports_flagged.get(src, set())
        if not knip_match:
            continue
        out.append(
            IntegrityIssue(
                rule="graph.dead_code",
                severity="WARN",
                node_id=n["id"],
                location=f"{src}:{n.get('source_location', 1) or 1}",
                message="Symbol unreferenced (knip+graph triple-confirm)",
                evidence={"vulture": False, "knip": True, "graph_orphan": True},
                fix_class="delete_dead_code",
            )
        )
    return out


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    thresholds = config.get("thresholds", {})
    min_conf = int(thresholds.get("vulture_min_confidence", 80))
    ignored = set(config.get("ignored_dead_code", []))

    backend_app = ctx.repo_root / "backend" / "app"
    frontend_dir = ctx.repo_root / "frontend"

    vulture_result = _run_vulture(backend_app, min_conf) if backend_app.exists() else VultureResult()
    knip_result = _run_knip(frontend_dir) if (frontend_dir / "package.json").exists() else KnipResult()

    orphans = set(find_orphans(ctx.graph))

    return [
        *_python_dead_code(ctx, orphans, vulture_result, ignored),
        *_frontend_dead_code(ctx, orphans, knip_result, ignored),
    ]
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_dead_code.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/rules/dead_code.py \
        backend/tests/integrity/plugins/graph_lint/rules/test_dead_code.py
git commit -m "feat(integrity): graph.dead_code rule — triple-intersect vulture/knip/graph"
```

---

## Task 13: Rule — `graph.drift_added` / `graph.drift_removed`

**Files:**
- Create: `backend/app/integrity/plugins/graph_lint/git_renames.py`
- Modify: `backend/app/integrity/plugins/graph_lint/rules/drift.py`
- Test: `backend/tests/integrity/plugins/graph_lint/test_git_renames.py`
- Test: `backend/tests/integrity/plugins/graph_lint/rules/test_drift.py`

Diff today's `GraphSnapshot` against yesterday's snapshot file. Apply `excluded_paths` globs. `drift_removed` downgrades to INFO when `git log --diff-filter=R --since=24h` reports a matching rename for the node's source file.

- [ ] **Step 1: Write the failing test for git rename parser**

```python
# backend/tests/integrity/plugins/graph_lint/test_git_renames.py
import subprocess

import pytest

from backend.app.integrity.plugins.graph_lint.git_renames import (
    parse_renames,
    recent_renames,
)


SAMPLE = """\
R100\told/path.py\tnew/path.py
R092\tfrontend/src/old.tsx\tfrontend/src/renamed.tsx
"""


def test_parse_extracts_old_to_new():
    renames = parse_renames(SAMPLE)
    assert renames == {
        "old/path.py": "new/path.py",
        "frontend/src/old.tsx": "frontend/src/renamed.tsx",
    }


def test_parse_handles_empty_input():
    assert parse_renames("") == {}


def test_recent_renames_swallows_subprocess_error(tmp_path, monkeypatch):
    # Pretend git is missing.
    monkeypatch.setenv("PATH", "/nonexistent")
    out = recent_renames(tmp_path, since="1.day.ago", git_bin="definitely_not_git")
    assert out == {}
```

- [ ] **Step 2: Implement git renames helper**

```python
# backend/app/integrity/plugins/graph_lint/git_renames.py
from __future__ import annotations

import subprocess
from pathlib import Path


def parse_renames(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].startswith("R"):
            old, new = parts[1], parts[2]
            out[old] = new
    return out


def recent_renames(
    repo_root: Path, *, since: str = "1.day.ago", git_bin: str = "git"
) -> dict[str, str]:
    cmd = [git_bin, "log", f"--since={since}", "--diff-filter=R", "--name-status", "--format="]
    try:
        proc = subprocess.run(
            cmd, cwd=str(repo_root), capture_output=True, text=True, check=False, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}
    return parse_renames(proc.stdout)
```

- [ ] **Step 3: Run rename parser test**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/test_git_renames.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Write the failing test for drift rules**

```python
# backend/tests/integrity/plugins/graph_lint/rules/test_drift.py
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.integrity.plugins.graph_lint.rules import drift
from backend.app.integrity.plugins.graph_lint.snapshots_test_helpers import write_snap_for_test  # noqa: F401  (created below)
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot
from backend.app.integrity.snapshots import write_snapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_drift_added_emits_for_new_node(repo: Path):
    yesterday = {"nodes": [{"id": "old", "source_file": "x.py"}], "links": []}
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(
        nodes=[{"id": "old", "source_file": "x.py"}, {"id": "new", "source_file": "y.py"}],
        links=[],
    )
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = drift.run_added(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["new"]
    assert all(i.severity == "INFO" for i in issues)


def test_drift_removed_emits_warn_for_removed_node(repo: Path):
    yesterday = {
        "nodes": [{"id": "old", "source_file": "x.py"}, {"id": "kept", "source_file": "y.py"}],
        "links": [],
    }
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(
        nodes=[{"id": "kept", "source_file": "y.py"}],
        links=[],
    )
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    with patch.object(drift, "recent_renames", return_value={}):
        issues = drift.run_removed(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["old"]
    assert all(i.severity == "WARN" for i in issues)


def test_drift_removed_downgrades_to_info_on_rename(repo: Path):
    yesterday = {"nodes": [{"id": "old_node", "source_file": "old/x.py"}], "links": []}
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(
        nodes=[{"id": "renamed_node", "source_file": "new/x.py"}],
        links=[],
    )
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    with patch.object(drift, "recent_renames", return_value={"old/x.py": "new/x.py"}):
        issues = drift.run_removed(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert [i.severity for i in issues] == ["INFO"]


def test_drift_excludes_test_paths(repo: Path):
    yesterday = {"nodes": [{"id": "old_test", "source_file": "tests/x_test.py"}], "links": []}
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(nodes=[], links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    with patch.object(drift, "recent_renames", return_value={}):
        issues = drift.run_removed(ctx, {"excluded_paths": ["tests/**"]}, date(2026, 4, 17))
    assert issues == []


def test_drift_no_baseline_emits_info_once(repo: Path):
    today_graph = GraphSnapshot(nodes=[{"id": "x", "source_file": "x.py"}], links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = drift.run_added(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.drift.no_baseline"
    assert issues[0].severity == "INFO"
```

- [ ] **Step 5: Implement drift rule**

```python
# backend/app/integrity/plugins/graph_lint/rules/drift.py
from __future__ import annotations

import fnmatch
from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....snapshots import load_snapshot_by_age
from ..git_renames import recent_renames


def _matches_any_glob(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _node_index(snap_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in snap_payload.get("nodes", [])}


def _no_baseline_issue() -> IntegrityIssue:
    return IntegrityIssue(
        rule="graph.drift.no_baseline",
        severity="INFO",
        node_id="<no-baseline>",
        location="integrity-out/snapshots/",
        message="Yesterday's snapshot missing — drift evaluation skipped (first runs only).",
        evidence={},
    )


def run_added(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    yesterday = load_snapshot_by_age(ctx.repo_root, days=1, today=today)
    if yesterday is None:
        return [_no_baseline_issue()]
    excluded = list(config.get("excluded_paths", []))
    yest_index = _node_index(yesterday)
    issues: list[IntegrityIssue] = []
    for node in ctx.graph.nodes:
        nid = node["id"]
        if nid in yest_index:
            continue
        src = node.get("source_file", "") or ""
        if _matches_any_glob(src, excluded):
            continue
        issues.append(
            IntegrityIssue(
                rule="graph.drift_added",
                severity="INFO",
                node_id=nid,
                location=src or "<unknown>",
                message=f"Node {nid!r} added since yesterday",
                evidence={},
            )
        )
    return issues


def run_removed(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    yesterday = load_snapshot_by_age(ctx.repo_root, days=1, today=today)
    if yesterday is None:
        return [_no_baseline_issue()]
    excluded = list(config.get("excluded_paths", []))
    today_ids = {n["id"] for n in ctx.graph.nodes}
    renames = recent_renames(ctx.repo_root, since="1.day.ago")
    issues: list[IntegrityIssue] = []
    for node in yesterday.get("nodes", []):
        nid = node["id"]
        if nid in today_ids:
            continue
        src = node.get("source_file", "") or ""
        if _matches_any_glob(src, excluded):
            continue
        was_renamed = src in renames
        severity = "INFO" if was_renamed else "WARN"
        msg_suffix = f" (file renamed → {renames[src]})" if was_renamed else ""
        issues.append(
            IntegrityIssue(
                rule="graph.drift_removed",
                severity=severity,
                node_id=nid,
                location=src or "<unknown>",
                message=f"Node {nid!r} removed since yesterday{msg_suffix}",
                evidence={"renamed_to": renames.get(src)} if was_renamed else {},
            )
        )
    return issues
```

- [ ] **Step 6: Run drift tests**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_drift.py -v
```
Expected: 5 passed.

- [ ] **Step 7: Remove the unused helper import in test (clean up)**

The line `from backend.app.integrity.plugins.graph_lint.snapshots_test_helpers import write_snap_for_test` was a placeholder hint. Confirm it isn't used and delete it from the test if present.

```bash
grep -n "snapshots_test_helpers" backend/tests/integrity/plugins/graph_lint/rules/test_drift.py
```
If found, edit it out.

- [ ] **Step 8: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/git_renames.py \
        backend/app/integrity/plugins/graph_lint/rules/drift.py \
        backend/tests/integrity/plugins/graph_lint/test_git_renames.py \
        backend/tests/integrity/plugins/graph_lint/rules/test_drift.py
git commit -m "feat(integrity): graph.drift_added/removed with rename downgrade + no-baseline INFO"
```

---

## Task 14: Rule — `graph.density_drop`

**Files:**
- Modify: `backend/app/integrity/plugins/graph_lint/rules/density_drop.py`
- Test: `backend/tests/integrity/plugins/graph_lint/rules/test_density_drop.py`

For each Python module, density = `intra_module_extracted_calls / module_node_count`. Compare today vs 7-days-ago snapshot. Emit if today < 0.75 × baseline. Skip when either side has < `module_min_nodes`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/rules/test_density_drop.py
from datetime import date
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_lint.rules import density_drop
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot
from backend.app.integrity.snapshots import write_snapshot


def make_module(name: str, num_nodes: int, num_edges: int) -> tuple[list[dict], list[dict]]:
    nodes = [
        {"id": f"{name}_n{i}", "source_file": f"backend/app/{name}.py", "kind": "function"}
        for i in range(num_nodes)
    ]
    links = []
    for i in range(num_edges):
        a, b = f"{name}_n{i % num_nodes}", f"{name}_n{(i + 1) % num_nodes}"
        links.append({"source": a, "target": b, "relation": "calls", "confidence": "EXTRACTED"})
    return nodes, links


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_emits_when_density_drops_more_than_25pct(repo: Path):
    week_nodes, week_links = make_module("m", 10, 20)
    write_snapshot(repo, {"nodes": week_nodes, "links": week_links}, today=date(2026, 4, 10))
    today_nodes, today_links = make_module("m", 10, 10)  # density: 1.0 vs 2.0 → 50% drop
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert len(issues) == 1
    assert "backend/app/m.py" in issues[0].location


def test_no_emit_when_drop_under_threshold(repo: Path):
    week_nodes, week_links = make_module("m", 10, 20)
    write_snapshot(repo, {"nodes": week_nodes, "links": week_links}, today=date(2026, 4, 10))
    today_nodes, today_links = make_module("m", 10, 18)  # 10% drop
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert issues == []


def test_skips_small_modules(repo: Path):
    week_nodes, week_links = make_module("tiny", 4, 8)
    write_snapshot(repo, {"nodes": week_nodes, "links": week_links}, today=date(2026, 4, 10))
    today_nodes, today_links = make_module("tiny", 4, 0)
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert issues == []


def test_no_baseline_emits_info(repo: Path):
    today_nodes, today_links = make_module("m", 10, 10)
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert len(issues) == 1
    assert issues[0].rule == "graph.density_drop.no_baseline"
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_density_drop.py -v
```
Expected: failures.

- [ ] **Step 3: Implement density_drop rule**

```python
# backend/app/integrity/plugins/graph_lint/rules/density_drop.py
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....snapshots import load_snapshot_by_age


def _module_stats(nodes: list[dict], links: list[dict]) -> dict[str, tuple[int, int]]:
    """Return {source_file: (node_count, intra_module_edge_count)} for Python modules."""
    nodes_by_file: dict[str, set[str]] = defaultdict(set)
    for n in nodes:
        src = n.get("source_file", "") or ""
        if not src.endswith(".py"):
            continue
        nodes_by_file[src].add(n["id"])

    node_to_file: dict[str, str] = {}
    for src, ids in nodes_by_file.items():
        for nid in ids:
            node_to_file[nid] = src

    edges_per_file: dict[str, int] = defaultdict(int)
    for link in links:
        if link.get("confidence") != "EXTRACTED":
            continue
        sfile = node_to_file.get(link.get("source", ""))
        tfile = node_to_file.get(link.get("target", ""))
        if sfile is None or tfile is None or sfile != tfile:
            continue
        edges_per_file[sfile] += 1

    return {src: (len(ids), edges_per_file[src]) for src, ids in nodes_by_file.items()}


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    thresholds = config.get("thresholds", {})
    drop_pct = float(thresholds.get("density_drop_pct", 25))
    min_nodes = int(thresholds.get("module_min_nodes", 5))

    week = load_snapshot_by_age(ctx.repo_root, days=7, today=today)
    if week is None:
        return [
            IntegrityIssue(
                rule="graph.density_drop.no_baseline",
                severity="INFO",
                node_id="<no-baseline>",
                location="integrity-out/snapshots/",
                message="7-day-old snapshot missing — density_drop evaluation skipped.",
                evidence={},
            )
        ]

    today_stats = _module_stats(ctx.graph.nodes, ctx.graph.links)
    week_stats = _module_stats(week.get("nodes", []), week.get("links", []))

    threshold_factor = 1.0 - (drop_pct / 100.0)
    issues: list[IntegrityIssue] = []
    for src, (today_n, today_e) in today_stats.items():
        if today_n < min_nodes:
            continue
        if src not in week_stats:
            continue
        week_n, week_e = week_stats[src]
        if week_n < min_nodes:
            continue
        today_density = today_e / today_n
        week_density = week_e / week_n
        if week_density == 0:
            continue
        if today_density < threshold_factor * week_density:
            pct_drop = round((1 - today_density / week_density) * 100, 1)
            issues.append(
                IntegrityIssue(
                    rule="graph.density_drop",
                    severity="WARN",
                    node_id=src,
                    location=src,
                    message=f"Module density dropped {pct_drop}% week-over-week",
                    evidence={
                        "today_density": round(today_density, 3),
                        "week_density": round(week_density, 3),
                        "drop_pct": pct_drop,
                    },
                )
            )
    return issues
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_density_drop.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/rules/density_drop.py \
        backend/tests/integrity/plugins/graph_lint/rules/test_density_drop.py
git commit -m "feat(integrity): graph.density_drop per-module WoW comparison"
```

---

## Task 15: Rule — `graph.orphan_growth`

**Files:**
- Modify: `backend/app/integrity/plugins/graph_lint/rules/orphan_growth.py`
- Test: `backend/tests/integrity/plugins/graph_lint/rules/test_orphan_growth.py`

Whole-graph signal: `today_orphan_count > 1.20 × week_orphan_count`. Single WARN when triggered. INFO `no_baseline` when 7d snapshot missing.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/rules/test_orphan_growth.py
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.integrity.plugins.graph_lint.rules import orphan_growth
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot
from backend.app.integrity.snapshots import write_snapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def make_orphans(n: int) -> list[dict]:
    return [
        {"id": f"orphan_{i}", "label": f"o{i}", "file_type": "code",
         "source_file": f"backend/app/o{i}.py", "kind": "function"}
        for i in range(n)
    ]


def test_emit_when_orphans_grow_more_than_20pct(repo: Path):
    write_snapshot(repo, {"nodes": make_orphans(10), "links": []}, today=date(2026, 4, 10))
    today_graph = GraphSnapshot(nodes=make_orphans(13), links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = orphan_growth.run(ctx, {"thresholds": {"orphan_growth_pct": 20}}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.orphan_growth"


def test_no_emit_when_growth_under_threshold(repo: Path):
    write_snapshot(repo, {"nodes": make_orphans(10), "links": []}, today=date(2026, 4, 10))
    today_graph = GraphSnapshot(nodes=make_orphans(11), links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = orphan_growth.run(ctx, {"thresholds": {"orphan_growth_pct": 20}}, date(2026, 4, 17))
    assert issues == []


def test_no_baseline_emits_info(repo: Path):
    today_graph = GraphSnapshot(nodes=make_orphans(5), links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = orphan_growth.run(ctx, {"thresholds": {"orphan_growth_pct": 20}}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.orphan_growth.no_baseline"
```

- [ ] **Step 2: Run to confirm failures**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_orphan_growth.py -v
```
Expected: failures.

- [ ] **Step 3: Implement orphan_growth rule**

```python
# backend/app/integrity/plugins/graph_lint/rules/orphan_growth.py
from __future__ import annotations

from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext
from ....schema import GraphSnapshot
from ....snapshots import load_snapshot_by_age
from ..orphans import find_orphans


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    thresholds = config.get("thresholds", {})
    growth_pct = float(thresholds.get("orphan_growth_pct", 20))

    week = load_snapshot_by_age(ctx.repo_root, days=7, today=today)
    if week is None:
        return [
            IntegrityIssue(
                rule="graph.orphan_growth.no_baseline",
                severity="INFO",
                node_id="<no-baseline>",
                location="integrity-out/snapshots/",
                message="7-day-old snapshot missing — orphan_growth evaluation skipped.",
                evidence={},
            )
        ]

    today_count = len(find_orphans(ctx.graph))
    week_snap = GraphSnapshot(nodes=week.get("nodes", []), links=week.get("links", []))
    week_count = len(find_orphans(week_snap))

    if week_count == 0:
        return []

    growth_factor = 1.0 + (growth_pct / 100.0)
    if today_count <= growth_factor * week_count:
        return []

    pct = round((today_count / week_count - 1) * 100, 1)
    return [
        IntegrityIssue(
            rule="graph.orphan_growth",
            severity="WARN",
            node_id="<global>",
            location="<whole-graph>",
            message=f"Orphan count grew {pct}% week-over-week ({week_count} → {today_count})",
            evidence={"today": today_count, "week_ago": week_count, "growth_pct": pct},
        )
    ]
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_orphan_growth.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/rules/orphan_growth.py \
        backend/tests/integrity/plugins/graph_lint/rules/test_orphan_growth.py
git commit -m "feat(integrity): graph.orphan_growth whole-graph WoW comparison"
```

---

## Task 16: Rule — `graph.handler_unbound`

**Files:**
- Modify: `backend/app/integrity/plugins/graph_lint/rules/handler_unbound.py`
- Test: `backend/tests/integrity/plugins/graph_lint/rules/test_handler_unbound.py`

A function node under `backend/app/api/**` or `backend/app/harness/**` whose name doesn't start with `_` and that has no inbound `routes_to` edge in the merged graph.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/plugins/graph_lint/rules/test_handler_unbound.py
from datetime import date
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_lint.rules import handler_unbound
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_emits_for_handler_without_routes_to(repo: Path):
    nodes = [
        {"id": "x_get_users", "label": "get_users", "file_type": "code",
         "source_file": "backend/app/api/x.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["x_get_users"]


def test_skips_handler_with_routes_to_edge(repo: Path):
    nodes = [
        {"id": "route_get_users", "label": "GET /users", "file_type": "code",
         "source_file": "backend/app/api/x.py"},
        {"id": "x_get_users", "label": "get_users", "file_type": "code",
         "source_file": "backend/app/api/x.py", "kind": "function"},
    ]
    links = [{"source": "route_get_users", "target": "x_get_users", "relation": "routes_to", "confidence": "EXTRACTED"}]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=links))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert issues == []


def test_skips_underscore_prefixed_functions(repo: Path):
    nodes = [
        {"id": "x__internal_helper", "label": "_internal_helper", "file_type": "code",
         "source_file": "backend/app/api/x.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert issues == []


def test_skips_non_api_paths(repo: Path):
    nodes = [
        {"id": "x_helper", "label": "helper", "file_type": "code",
         "source_file": "backend/app/lib/x.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert issues == []


def test_includes_harness_paths(repo: Path):
    nodes = [
        {"id": "h_run", "label": "run", "file_type": "code",
         "source_file": "backend/app/harness/h.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["h_run"]
```

- [ ] **Step 2: Run to confirm failures**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_handler_unbound.py -v
```
Expected: failures.

- [ ] **Step 3: Implement handler_unbound rule**

```python
# backend/app/integrity/plugins/graph_lint/rules/handler_unbound.py
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from ....issue import IntegrityIssue
from ....protocol import ScanContext

_HANDLER_PATH_PREFIXES = ("backend/app/api/", "backend/app/harness/")


def run(ctx: ScanContext, config: dict[str, Any], today: date) -> list[IntegrityIssue]:
    routes_to_targets: set[str] = set()
    for link in ctx.graph.links:
        if link.get("relation") == "routes_to" and link.get("confidence") == "EXTRACTED":
            routes_to_targets.add(link["target"])

    issues: list[IntegrityIssue] = []
    for node in ctx.graph.nodes:
        if node.get("kind") != "function":
            continue
        src = node.get("source_file", "") or ""
        if not any(src.startswith(p) for p in _HANDLER_PATH_PREFIXES):
            continue
        label = node.get("label", "")
        if not label or label.startswith("_"):
            continue
        if node["id"] in routes_to_targets:
            continue
        issues.append(
            IntegrityIssue(
                rule="graph.handler_unbound",
                severity="WARN",
                node_id=node["id"],
                location=src,
                message=f"Handler {label!r} has no inbound routes_to edge",
                evidence={},
            )
        )
    return issues
```

- [ ] **Step 4: Run to confirm passes**

```
uv run pytest backend/tests/integrity/plugins/graph_lint/rules/test_handler_unbound.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_lint/rules/handler_unbound.py \
        backend/tests/integrity/plugins/graph_lint/rules/test_handler_unbound.py
git commit -m "feat(integrity): graph.handler_unbound flags FastAPI handlers without routes_to"
```

---

## Task 17: Engine A→B integration test

**Files:**
- Modify: `backend/tests/integrity/test_engine_pipeline.py`

Add a real-plugin integration test that runs A then B against a tiny synthetic repo and asserts the engine wires them correctly.

- [ ] **Step 1: Append integration test to existing file**

```python
# Append to backend/tests/integrity/test_engine_pipeline.py

import json
from datetime import date

from backend.app.integrity.plugins.graph_extension.plugin import GraphExtensionPlugin
from backend.app.integrity.plugins.graph_lint.plugin import GraphLintPlugin


def test_real_pipeline_runs_a_then_b(tmp_path):
    (tmp_path / "graphify").mkdir()
    (tmp_path / "graphify" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "x_helper", "label": "helper", "file_type": "code",
                   "source_file": "backend/app/x.py", "kind": "function"}],
        "links": [],
    }))
    (tmp_path / "backend" / "app" / "api").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "api" / "__init__.py").write_text("")
    (tmp_path / "backend" / "app" / "api" / "users.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/users')\n"
        "def list_users():\n    return []\n"
    )

    engine = IntegrityEngine(tmp_path)
    engine.register(GraphExtensionPlugin())
    engine.register(GraphLintPlugin(today=date(2026, 4, 17)))
    results = engine.run()

    assert [r.plugin_name for r in results] == ["graph_extension", "graph_lint"]
    # No exceptions surfaced as engine.plugin_failed:
    for r in results:
        assert all(i.rule != "engine.plugin_failed" for i in r.issues), [
            (i.rule, i.message) for i in r.issues
        ]
```

- [ ] **Step 2: Run**

```
uv run pytest backend/tests/integrity/test_engine_pipeline.py -v
```
Expected: previous 4 + 1 new = 5 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integrity/test_engine_pipeline.py
git commit -m "test(integrity): A→B pipeline integration test"
```

---

## Task 18: Config file, .gitignore, Makefile, vulture dep verification

**Files:**
- Create: `config/integrity.yaml`
- Modify: `.gitignore`
- Modify: `Makefile`

Ship the committed config + Makefile entries + ignore.

- [ ] **Step 1: Create `config/integrity.yaml`**

```yaml
# config/integrity.yaml
plugins:
  graph_extension:
    enabled: true
  graph_lint:
    enabled: true
    thresholds:
      vulture_min_confidence: 80      # passed to vulture --min-confidence
      density_drop_pct: 25            # >25% WoW drop → WARN
      orphan_growth_pct: 20           # >20% WoW growth → WARN
      module_min_nodes: 5             # density_drop ignores smaller modules
      snapshot_retention_days: 30     # prune older snapshots
    ignored_dead_code: []             # list of node_ids
    excluded_paths:
      - "tests/**"
      - "**/migrations/**"
      - "**/__pycache__/**"
```

- [ ] **Step 2: Append to `.gitignore`**

```
# Integrity engine outputs (per docs/superpowers/specs/2026-04-17-integrity-plugin-b-design.md §7)
integrity-out/
```

- [ ] **Step 3: Add Makefile targets**

Append to `Makefile`:

```makefile
.PHONY: integrity integrity-lint integrity-snapshot-prune

integrity: ## Run the full integrity pipeline (A→B); writes integrity-out/ + docs/health/
	uv run python -m backend.app.integrity

integrity-lint: ## Run only Plugin B (graph_lint) — assumes A has run
	uv run python -m backend.app.integrity --plugin graph_lint --no-augment

integrity-snapshot-prune: ## Prune integrity-out/snapshots/ older than 30 days
	uv run python -c "from datetime import date; from pathlib import Path; from backend.app.integrity.snapshots import prune_older_than; n = prune_older_than(Path.cwd(), days=30, today=date.today()); print(f'pruned {n}')"
```

- [ ] **Step 4: Smoke-run the Makefile target (no augment to keep it fast)**

```
make integrity-lint 2>&1 | tail -20
```
Expected: completes; writes `integrity-out/{today}/`. (Vulture/knip may produce real findings — that's fine.)

- [ ] **Step 5: Commit**

```bash
git add config/integrity.yaml .gitignore Makefile
git commit -m "feat(integrity): config/integrity.yaml + Makefile integrity targets + ignore integrity-out"
```

---

## Task 19: FastAPI static mount for `docs/health/`

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/integrity/test_health_static_mount.py`

Backend serves committed `docs/health/*.md` so the frontend can fetch `/static/health/latest.md` without an API endpoint. Mount only if directory exists (covers fresh clones before first run).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrity/test_health_static_mount.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    health = tmp_path / "docs" / "health"
    health.mkdir(parents=True)
    (health / "latest.md").write_text("# Hello health\n")
    monkeypatch.chdir(tmp_path)
    # Re-import main with new cwd so the mount picks up our docs/health
    import importlib

    import backend.app.main as main
    importlib.reload(main)
    return TestClient(main.app)


def test_serves_latest_md(client: TestClient):
    resp = client.get("/static/health/latest.md")
    assert resp.status_code == 200
    assert "Hello health" in resp.text
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest backend/tests/integrity/test_health_static_mount.py -v
```
Expected: 404 (mount missing).

- [ ] **Step 3: Add mount to `backend/app/main.py`**

Inspect the existing `main.py` and locate where `app = FastAPI(...)` is constructed and other mounts/middlewares are registered. Add this near other mount declarations:

```python
# backend/app/main.py — add near existing mounts (do not duplicate the FastAPI() construction)
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_health_dir = Path.cwd() / "docs" / "health"
if _health_dir.is_dir():
    app.mount("/static/health", StaticFiles(directory=str(_health_dir)), name="health-static")
```

If `main.py` already has a static-mount section, place this block alongside others rather than at the bottom.

- [ ] **Step 4: Run test**

```
uv run pytest backend/tests/integrity/test_health_static_mount.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/integrity/test_health_static_mount.py
git commit -m "feat(integrity): mount docs/health/ at /static/health for frontend rendering"
```

---

## Task 20: Frontend Health section + IconRail entry

**Files:**
- Modify: `frontend/src/lib/store.ts` (add `'health'` to `SectionId`)
- Modify: `frontend/src/components/layout/IconRail.tsx` (add entry)
- Create: `frontend/src/sections/HealthSection.tsx`
- Modify: `frontend/src/App.tsx` (switch case)
- Test: `frontend/src/sections/__tests__/HealthSection.test.tsx`

Renders `docs/health/latest.md` via existing `MarkdownContent`. Empty state when the file is missing.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/sections/__tests__/HealthSection.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { HealthSection } from '../HealthSection'

describe('HealthSection', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    global.fetch = vi.fn()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('renders the markdown when fetch succeeds', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      text: () => Promise.resolve('# Hello health\n\nbody'),
    })
    render(<HealthSection />)
    await waitFor(() => {
      expect(screen.getByText(/Hello health/)).toBeInTheDocument()
    })
  })

  it('shows empty state when fetch returns 404', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: () => Promise.resolve(''),
    })
    render(<HealthSection />)
    await waitFor(() => {
      expect(screen.getByText(/No integrity report yet/i)).toBeInTheDocument()
    })
  })
})
```

- [ ] **Step 2: Run to confirm failure**

```
cd frontend && npx vitest run src/sections/__tests__/HealthSection.test.tsx
```
Expected: file/import error.

- [ ] **Step 3: Add `'health'` to SectionId**

In `frontend/src/lib/store.ts:49`:

```typescript
// before:
export type SectionId = 'chat' | 'agents' | 'skills' | 'prompts' | 'context' | 'devtools' | 'settings'
// after:
export type SectionId = 'chat' | 'agents' | 'skills' | 'prompts' | 'context' | 'devtools' | 'health' | 'settings'
```

- [ ] **Step 4: Add Health entry to IconRail**

Edit `frontend/src/components/layout/IconRail.tsx` — add `Activity` (or another lucide icon) to the import and an entry to `TOP_SECTIONS`:

```tsx
import {
  MessageSquare,
  Monitor,
  Puzzle,
  FileText,
  Layers,
  Code2,
  Activity,
  Settings,
} from 'lucide-react'

const TOP_SECTIONS: SectionDef[] = [
  { id: 'chat', icon: MessageSquare, label: 'Chat' },
  { id: 'agents', icon: Monitor, label: 'Agents' },
  { id: 'skills', icon: Puzzle, label: 'Skills' },
  { id: 'prompts', icon: FileText, label: 'Prompts' },
  { id: 'context', icon: Layers, label: 'Context' },
  { id: 'devtools', icon: Code2, label: 'DevTools' },
  { id: 'health', icon: Activity, label: 'Health' },
]
```

- [ ] **Step 5: Create HealthSection**

```tsx
// frontend/src/sections/HealthSection.tsx
import { useEffect, useState } from 'react'
import { MarkdownContent } from '@/components/chat/MarkdownContent'

export function HealthSection() {
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch('/static/health/latest.md')
      .then(async (r) => {
        if (cancelled) return
        if (!r.ok) {
          setMissing(true)
          return
        }
        const text = await r.text()
        if (!cancelled) setMarkdown(text)
      })
      .catch(() => {
        if (!cancelled) setMissing(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (missing) {
    return (
      <div className="p-6 text-surface-300">
        <p className="text-sm">
          No integrity report yet. Run <code>make integrity</code> to generate one.
        </p>
      </div>
    )
  }
  if (markdown == null) {
    return <div className="p-6 text-surface-500 text-sm">Loading health report…</div>
  }
  return (
    <div className="p-6 max-w-4xl mx-auto overflow-y-auto h-full">
      <MarkdownContent content={markdown} />
    </div>
  )
}
```

- [ ] **Step 6: Add switch case to App.tsx**

In `frontend/src/App.tsx` near the existing section switch (around line 198), add the Health case and import:

```tsx
import { HealthSection } from '@/sections/HealthSection'
// ...inside the switch on activeSection:
    case 'health':
      return <HealthSection />
```

- [ ] **Step 7: Run unit test**

```
cd frontend && npx vitest run src/sections/__tests__/HealthSection.test.tsx
```
Expected: 2 passed.

- [ ] **Step 8: Run frontend type-check + linting**

```
cd frontend && npx tsc --noEmit && npx eslint src/sections/HealthSection.tsx src/components/layout/IconRail.tsx src/App.tsx src/lib/store.ts
```
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/store.ts \
        frontend/src/components/layout/IconRail.tsx \
        frontend/src/sections/HealthSection.tsx \
        frontend/src/sections/__tests__/HealthSection.test.tsx \
        frontend/src/App.tsx
git commit -m "feat(integrity): frontend Health section + sidebar rail entry"
```

---

## Task 21: E2E test for Health page

**Files:**
- Create: `frontend/e2e/health.spec.ts`

A Playwright test that opens the app, clicks the Health rail entry, and confirms content from `latest.md` renders.

- [ ] **Step 1: Confirm Playwright is configured**

```bash
ls frontend/playwright.config.ts frontend/e2e/ 2>&1
```
Expected: file exists. If not, skip this task and document the gap in audit.md.

- [ ] **Step 2: Write the E2E test**

```typescript
// frontend/e2e/health.spec.ts
import { test, expect } from '@playwright/test'

test('health rail entry navigates to health section', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Health' }).click()
  // Either the report renders or the empty-state message appears.
  await expect(
    page.locator('text=/No integrity report yet|Health —/i'),
  ).toBeVisible({ timeout: 5000 })
})
```

- [ ] **Step 3: Run the E2E test (skip if fixtures need backend running)**

```
cd frontend && npx playwright test e2e/health.spec.ts
```
Expected: passes if dev servers can start in test mode. If the test infra doesn't auto-start servers, document and skip.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/health.spec.ts
git commit -m "test(integrity): playwright E2E for Health rail entry"
```

---

## Task 22: Live first run + write `docs/log.md` entry

**Files:**
- Modify: `docs/log.md`

Run `make integrity` against the real repo. Verify all artifacts exist. Capture issue counts for the audit doc.

- [ ] **Step 1: Run the pipeline**

```
make integrity 2>&1 | tail -30
```
Expected: exit 0; logs show writes to `integrity-out/{today}/` and `docs/health/`.

- [ ] **Step 2: Verify artifacts**

```
ls -la integrity-out/$(date +%Y-%m-%d)/ && head -40 docs/health/latest.md && echo "--- trend ---" && cat docs/health/trend.md
```
Expected:
- `integrity-out/<today>/` contains `report.json`, `report.md`, `graph_lint.json`.
- `integrity-out/snapshots/<today>.json` exists.
- `docs/health/latest.md` shows summary + per-plugin sections.
- `docs/health/trend.md` shows today's row.

- [ ] **Step 3: Update changelog**

Append under `[Unreleased]` → `### Added` in `docs/log.md`:

```markdown
- **Integrity Plugin B — Graph Lint (gate β)**: nightly drift / dead-code / WoW signals via 5 rules — `graph.dead_code` (vulture+knip+graph triple-confirm), `graph.drift_added/removed` (with git-rename downgrade), `graph.density_drop` (per-module WoW), `graph.orphan_growth` (whole-graph WoW), `graph.handler_unbound` (FastAPI route w/o handler edge). Engine becomes the orchestrator: `GraphSnapshot.load` auto-merges `graph.augmented.json`, dispatches plugins in dependency order, catches per-plugin exceptions. Outputs: `integrity-out/{date}/report.{json,md}` (gitignored) + `docs/health/{latest,trend}.md` (committed). Trigger via `make integrity` (full A→B) or `make integrity-lint` (B only). Frontend gains a Health rail entry rendering `latest.md`. (`backend/app/integrity/`, `backend/tests/integrity/`, `frontend/src/sections/HealthSection.tsx`, `config/integrity.yaml`, `Makefile`, `.gitignore`)
```

- [ ] **Step 4: Commit live-run artifacts that are committed-by-design**

```bash
git add docs/health/latest.md docs/health/trend.md docs/log.md
git commit -m "chore(integrity): first live integrity run — health/latest.md + trend.md initial state"
```

---

## Task 23: Gate β manual dead-code audit

**Files:**
- Create: `docs/health/audit-2026-04-17.md`

Sample first 20 `graph.dead_code` issues from today's `report.json`. For each: open the file, search for callers (rg/grep), confirm dead. Mark verified-dead vs false-positive. Pass requires ≥16/20.

- [ ] **Step 1: Extract today's dead_code issues**

```bash
uv run python -c "
import json
from datetime import date
from pathlib import Path

p = Path('integrity-out') / date.today().isoformat() / 'graph_lint.json'
data = json.loads(p.read_text())
dc = [i for i in data['issues'] if i['rule'] == 'graph.dead_code']
print(f'total dead_code: {len(dc)}')
for i in dc[:20]:
    print(f'- {i[\"node_id\"]:50s} {i[\"location\"]}  evidence={i[\"evidence\"]}')
" | tee /tmp/dead-code-sample.txt
```

- [ ] **Step 2: Branch on sample size**

If `total dead_code` < 5: re-run with lowered confidence to surface a denser sample for one-time audit:

```
INTEGRITY_VULTURE_MIN_CONFIDENCE=60 make integrity-lint
```

Then re-extract.

- [ ] **Step 3: Manually verify each issue**

For each of 20 sampled issues:
1. Open the file at the listed location.
2. Run `rg -nF "<symbol_name>" backend/ frontend/ scripts/ docs/ 2>/dev/null | head -10` to find references (excluding the definition itself).
3. Mark "verified dead" or "FALSE POSITIVE — used in <where>".

- [ ] **Step 4: Write audit doc**

```markdown
# Integrity gate β — `graph.dead_code` audit (2026-04-17)

**Sample size:** 20 issues from today's run.
**Result:** XX/20 verified-dead (target: ≥16/20 = 80%).
**Verdict:** PASS / FAIL.

## Methodology

1. Sampled the first 20 `graph.dead_code` issues from `integrity-out/2026-04-17/graph_lint.json`.
2. For each: opened the file at the reported location, searched the codebase with ripgrep for any references to the symbol (excluding the definition line itself), and marked verified-dead if no real call site was found.
3. Counted false positives — "live" usages the rule missed.

## Per-issue findings

| # | node_id | location | evidence | result |
|---|---------|----------|----------|--------|
| 1 | … | … | vulture+orphan | ✅ verified dead |
| 2 | … | … | knip+orphan | ❌ FALSE POSITIVE — referenced in … |
| … | | | | |

## Notes

- (List FP categories observed.)
- (Note any threshold tweaks recommended for next run.)
```

(Replace placeholders with actual data from the manual review.)

- [ ] **Step 5: Verify gate**

If ≥16/20 verified-dead: PASS. Document in spec / log.

If <16/20: do NOT lower the gate. Tighten one of:
- `vulture_min_confidence` (raise to 90)
- knip config (add stricter `entry` paths)
- `excluded_paths` (add specific globs the FPs share)

Re-run, re-audit. Repeat until pass.

- [ ] **Step 6: Commit audit doc**

```bash
git add docs/health/audit-2026-04-17.md
git commit -m "chore(integrity): gate β dead_code audit — XX/20 verified-dead"
```

(Replace `XX` with the real count in the actual commit message.)

---

## Task 24: Final smoke + cross-plugin regression check

**Files:**
- (no new files; verification only)

Run the full integrity suite one more time, run the existing test suite to confirm no regressions, sanity-check the live frontend.

- [ ] **Step 1: Full backend test suite**

```
uv run pytest backend/tests/ -q
```
Expected: all tests green; new graph_lint tests included.

- [ ] **Step 2: Frontend unit tests**

```
cd frontend && npx vitest run --silent && cd ..
```
Expected: green (HealthSection tests included).

- [ ] **Step 3: Lint + typecheck**

```
make lint && make typecheck
```
Expected: clean.

- [ ] **Step 4: Re-run pipeline against live repo**

```
make integrity 2>&1 | tail -20
```
Expected: exit 0; second run uses yesterday's snapshot from Task 22 → drift_added/removed should now produce real (likely 0) issues instead of `no_baseline`.

- [ ] **Step 5: Boot frontend and click Health**

```
make dev &
# wait ~10s for vite + uvicorn
```

Open `http://localhost:5173`, click the Health rail entry. Confirm the report renders. Stop processes when done.

- [ ] **Step 6: Final commit if anything moved**

```bash
git status
# If docs/health/{latest,trend}.md changed since Task 22, stage and commit:
git add docs/health/latest.md docs/health/trend.md
git commit -m "chore(integrity): refresh health/latest.md after second pipeline run"
```

(If nothing changed: skip the commit.)

---

## Self-review notes

**Spec coverage check (against `2026-04-17-integrity-plugin-b-design.md`):**

| Spec section | Plan tasks | Notes |
|--------------|------------|-------|
| §1 Goal | 22, 23, 24 | Live run + gate audit + smoke |
| §2 Non-goals | (negative space) | No live API, no per-plugin cards, no autofix — none of these have tasks |
| §3 Decisions | 10, 11 (vulture+knip), 18 (config), 22 (engine wiring proven), 23 (audit), 4 (snapshots dated) | Each decision has a concrete task |
| §4 Architecture | 2, 3, 4, 5, 6, 7, 19 | Engine + schema + snapshots + report + CLI + static mount |
| §4.1 New/modified files | covered in `File Structure` table at top | All 30+ files mapped to tasks |
| §4.2 Plugin contract | 8 | `GraphLintPlugin` dataclass with depends_on |
| §5 The five rules | 12, 13, 14, 15, 16 | One task per rule |
| §6 Data flow | 7 (CLI), 6 (report), 4 (snapshots) | Per-run sequence implemented |
| §7 Storage layout | 18 (.gitignore + config), 6 (writes paths) | All paths covered |
| §8 Configuration | 5, 18 | Loader + committed YAML |
| §9 Frontend Health | 19, 20, 21 | Static mount + section + E2E |
| §10 Error handling | 3 (engine catch), 8 (per-rule catch), 13 (no_baseline INFO) | All paths covered |
| §11 Testing | every implementation task pairs with a test task | TDD throughout |
| §12 Acceptance gate | 22 (run) + 23 (audit) + 24 (smoke) | Three-task gate |
| §13 Risks | (negative space) | Mitigations live in tests + config |

**Placeholder scan:** No "TBD" / "implement later" / "fill in details" patterns. Two intentional template-style placeholders in `audit-2026-04-17.md` (the actual review numbers) — these get filled during execution, not in the plan.

**Type consistency:** `IntegrityIssue` shape locked in Task 1 and reused everywhere (Tasks 8, 12–16, 17). `ScanResult` typed in Task 3, used unchanged thereafter. Rule signature `(ctx, config, today) -> list[IntegrityIssue]` is identical across Tasks 8, 12–16. Snapshot helpers (`write_snapshot`, `load_snapshot_by_age`, `prune_older_than`) defined in Task 4, called with the same signatures in Tasks 7, 13, 14, 15.

**Plan complete and saved to `docs/superpowers/plans/2026-04-17-integrity-plugin-b.md`.** Per pre-approval, transitioning directly to subagent-driven-development.
