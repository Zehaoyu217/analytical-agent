# Integrity Plugin A — Graph Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Augment the graphify knowledge graph with FastAPI route handlers, intra-file Python calls, and React JSX usage edges. Drop the use-edge orphan false-positive rate from ~63% to <15% backend / <30% frontend.

**Architecture:** A minimal `IntegrityEngine` harness dispatches `IntegrityPlugin` instances. Plugin A (`graph_extension`) runs three independent extractors (Python `ast` for FastAPI + intra-file, Node `@babel/parser` subprocess for JSX), deduplicates output, writes `graphify/graph.augmented.json` with provenance markers. Stock graphify output is untouched; consumers merge with read-precedence.

**Tech Stack:** Python 3.12 stdlib `ast`, `dataclasses`, `pathlib`. Node 20+ with `@babel/parser`. Pytest. No new Python deps.

**Specs:**
- Sub-spec: `docs/superpowers/specs/2026-04-16-integrity-plugin-a-design.md`
- Parent: `docs/superpowers/specs/2026-04-16-integrity-system-design.md`

---

## File Structure

```
backend/app/integrity/
  __init__.py
  schema.py                          # GraphSnapshot loader
  protocol.py                        # IntegrityPlugin Protocol + ScanContext/Result
  engine.py                          # IntegrityEngine dispatch loop
  plugins/
    __init__.py
    graph_extension/
      __init__.py
      schema.py                      # ExtractedNode/Edge/Result, EXTENSION_TAG
      augmenter.py                   # Orchestrator: run extractors → dedupe → write JSON
      plugin.py                      # IntegrityPlugin entry (calls augmenter)
      cli.py                         # `python -m ...graph_extension`
      extractors/
        __init__.py
        _ast_helpers.py              # Shared _name_of, _extract_kw_str
        fastapi_routes.py
        intra_file_calls.py
        jsx_usage.py
        _node_helper/
          parse_jsx.mjs              # Node CLI using @babel/parser
          package.json               # Pinned deps
          .gitignore                 # node_modules
backend/tests/integrity/
  __init__.py
  conftest.py
  test_engine.py
  test_schema.py
  plugins/
    __init__.py
    graph_extension/
      __init__.py
      fixtures/
        fastapi_app/
          basic_router.py
          composed_router.py
          api_route_methods.py
          main_with_include.py
        intra_file/
          two_funcs.py
          self_method.py
          decorated_helpers.py
        jsx_app/
          Direct.tsx
          HOC.tsx
          LazyImport.tsx
          RenderProp.tsx
      test_fastapi_routes.py
      test_intra_file_calls.py
      test_jsx_usage.py
      test_augmenter.py
      test_plugin.py
scripts/
  verify_orphans.py                  # Relocated from /tmp
Makefile                             # Add `integrity-augment` target
```

---

## Task 1: Engine harness — schema + protocol

**Files:**
- Create: `backend/app/integrity/__init__.py`
- Create: `backend/app/integrity/schema.py`
- Create: `backend/app/integrity/protocol.py`
- Create: `backend/tests/integrity/__init__.py`
- Create: `backend/tests/integrity/conftest.py`
- Create: `backend/tests/integrity/test_schema.py`

- [ ] **Step 1: Write failing test for `GraphSnapshot.load`**

`backend/tests/integrity/test_schema.py`:

```python
from __future__ import annotations
import json
from pathlib import Path

from backend.app.integrity.schema import GraphSnapshot


def test_graph_snapshot_loads_from_graphify_dir(tmp_path: Path) -> None:
    graph_dir = tmp_path / "graphify"
    graph_dir.mkdir()
    payload = {"nodes": [{"id": "a"}, {"id": "b"}], "links": [{"source": "a", "target": "b"}]}
    (graph_dir / "graph.json").write_text(json.dumps(payload))

    snap = GraphSnapshot.load(tmp_path)

    assert snap.nodes == payload["nodes"]
    assert snap.links == payload["links"]


def test_graph_snapshot_load_missing_file_raises(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        GraphSnapshot.load(tmp_path)
```

`backend/tests/integrity/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.integrity'`

- [ ] **Step 3: Implement `GraphSnapshot`**

`backend/app/integrity/__init__.py`:

```python
"""Integrity engine + plugins for the self-maintaining doc/code/graph system.

See docs/superpowers/specs/2026-04-16-integrity-system-design.md.
"""
```

`backend/app/integrity/schema.py`:

```python
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
```

`backend/app/integrity/protocol.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .schema import GraphSnapshot


@dataclass(frozen=True)
class ScanContext:
    repo_root: Path
    graph: GraphSnapshot


@dataclass(frozen=True)
class ScanResult:
    plugin_name: str
    plugin_version: str
    issues: list[dict[str, Any]] = field(default_factory=list)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/test_schema.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/__init__.py backend/app/integrity/schema.py backend/app/integrity/protocol.py backend/tests/integrity/__init__.py backend/tests/integrity/conftest.py backend/tests/integrity/test_schema.py
git commit -m "feat(integrity): add IntegrityPlugin protocol and GraphSnapshot loader"
```

---

## Task 2: Engine harness — dispatch loop

**Files:**
- Create: `backend/app/integrity/engine.py`
- Create: `backend/tests/integrity/test_engine.py`

- [ ] **Step 1: Write failing test for `IntegrityEngine`**

`backend/tests/integrity/test_engine.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.integrity.engine'`

- [ ] **Step 3: Implement `IntegrityEngine`**

`backend/app/integrity/engine.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/test_engine.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/engine.py backend/tests/integrity/test_engine.py
git commit -m "feat(integrity): add IntegrityEngine dispatch loop"
```

---

## Task 3: Plugin A schema + relocate verify_orphans.py

**Files:**
- Create: `backend/app/integrity/plugins/__init__.py`
- Create: `backend/app/integrity/plugins/graph_extension/__init__.py`
- Create: `backend/app/integrity/plugins/graph_extension/schema.py`
- Create: `backend/tests/integrity/plugins/__init__.py`
- Create: `backend/tests/integrity/plugins/graph_extension/__init__.py`
- Create: `scripts/verify_orphans.py` (move from `/tmp/verify_orphans.py`)

- [ ] **Step 1: Move `verify_orphans.py` from /tmp to scripts/**

```bash
mkdir -p /Users/jay/Developer/claude-code-agent/scripts
cp /tmp/verify_orphans.py /Users/jay/Developer/claude-code-agent/scripts/verify_orphans.py
```

- [ ] **Step 2: Patch `verify_orphans.py` to also load augmented graph**

Edit `scripts/verify_orphans.py` — replace the `g = json.loads(GRAPH.read_text())` block (around line 10) with:

```python
g = json.loads(GRAPH.read_text())
AUG = REPO / "graphify" / "graph.augmented.json"
if AUG.exists():
    aug = json.loads(AUG.read_text())
    g["nodes"].extend(aug["nodes"])
    g["links"].extend(aug["links"])
```

- [ ] **Step 3: Create plugin A schema**

`backend/app/integrity/plugins/__init__.py`:

```python
"""Built-in integrity plugins."""
```

`backend/app/integrity/plugins/graph_extension/__init__.py`:

```python
"""Plugin A — augment graphify with FastAPI routes, intra-file calls, JSX usage.

See docs/superpowers/specs/2026-04-16-integrity-plugin-a-design.md.
"""
```

`backend/app/integrity/plugins/graph_extension/schema.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EXTENSION_TAG = "cca-v1"
ExtractorName = Literal["fastapi_routes", "intra_file_calls", "jsx_usage"]


@dataclass(frozen=True)
class ExtractedNode:
    id: str
    label: str
    file_type: str  # "code" | "route"
    source_file: str
    source_location: int | None
    extractor: ExtractorName


@dataclass(frozen=True)
class ExtractedEdge:
    source: str
    target: str
    relation: str  # "routes_to" | "calls" | "uses"
    source_file: str
    source_location: int | None
    extractor: ExtractorName
    confidence: str = "EXTRACTED"
    confidence_score: float = 1.0


@dataclass(frozen=True)
class ExtractionResult:
    nodes: list[ExtractedNode] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
```

`backend/tests/integrity/plugins/__init__.py` and `backend/tests/integrity/plugins/graph_extension/__init__.py`: empty files.

- [ ] **Step 4: Verify schema imports**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -c "from backend.app.integrity.plugins.graph_extension.schema import ExtractedNode, ExtractedEdge, ExtractionResult, EXTENSION_TAG; print(EXTENSION_TAG)"`
Expected: prints `cca-v1`

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_orphans.py backend/app/integrity/plugins/ backend/tests/integrity/plugins/
git commit -m "feat(integrity): add plugin-A schema and relocate verify_orphans.py"
```

---

## Task 4: Augmenter skeleton — empty extractors

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/augmenter.py`
- Create: `backend/tests/integrity/plugins/graph_extension/test_augmenter.py`

- [ ] **Step 1: Write failing test for empty-extractor augment**

`backend/tests/integrity/plugins/graph_extension/test_augmenter.py`:

```python
from __future__ import annotations
import json
from pathlib import Path

from backend.app.integrity.plugins.graph_extension.augmenter import augment
from backend.app.integrity.plugins.graph_extension.schema import (
    ExtractedEdge,
    ExtractedNode,
    ExtractionResult,
)


def _seed_graph(tmp_path: Path) -> None:
    g = tmp_path / "graphify"
    g.mkdir()
    (g / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))


def test_augment_with_no_extractors_writes_empty_outputs(tmp_path: Path) -> None:
    _seed_graph(tmp_path)
    manifest = augment(tmp_path, extractors=[])

    out = json.loads((tmp_path / "graphify" / "graph.augmented.json").read_text())
    assert out == {"nodes": [], "links": []}
    assert manifest["nodes_emitted"] == 0
    assert manifest["edges_emitted"] == 0
    assert manifest["extension"] == "cca-v1"


def test_augment_dedupes_nodes_by_id_and_edges_by_triple(tmp_path: Path) -> None:
    _seed_graph(tmp_path)

    def ext_a(repo, graph):
        return ExtractionResult(
            nodes=[ExtractedNode("n1", "L1", "code", "a.py", 1, "fastapi_routes")],
            edges=[ExtractedEdge("n1", "n2", "calls", "a.py", 1, "fastapi_routes")],
        )

    def ext_b(repo, graph):
        return ExtractionResult(
            nodes=[ExtractedNode("n1", "L1-dup", "code", "a.py", 1, "intra_file_calls")],
            edges=[ExtractedEdge("n1", "n2", "calls", "a.py", 5, "intra_file_calls")],
        )

    augment(tmp_path, extractors=[("a", ext_a), ("b", ext_b)])
    out = json.loads((tmp_path / "graphify" / "graph.augmented.json").read_text())
    assert len(out["nodes"]) == 1  # node id deduped
    assert len(out["links"]) == 1  # (source, target, relation) deduped
    assert out["nodes"][0]["extension"] == "cca-v1"


def test_augment_records_extractor_failure_in_manifest(tmp_path: Path) -> None:
    _seed_graph(tmp_path)

    def explode(repo, graph):
        raise RuntimeError("boom")

    manifest = augment(tmp_path, extractors=[("bad", explode)])
    assert any("boom" in f for f in manifest["failures"])


def test_augment_is_idempotent(tmp_path: Path) -> None:
    _seed_graph(tmp_path)

    def ext(repo, graph):
        return ExtractionResult(
            nodes=[ExtractedNode("n1", "L1", "code", "a.py", 1, "fastapi_routes")],
            edges=[],
        )

    augment(tmp_path, extractors=[("a", ext)])
    first = (tmp_path / "graphify" / "graph.augmented.json").read_bytes()
    augment(tmp_path, extractors=[("a", ext)])
    second = (tmp_path / "graphify" / "graph.augmented.json").read_bytes()
    assert first == second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_augmenter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named '...augmenter'`

- [ ] **Step 3: Implement `augment`**

`backend/app/integrity/plugins/graph_extension/augmenter.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ...schema import GraphSnapshot
from .schema import EXTENSION_TAG, ExtractedEdge, ExtractedNode, ExtractionResult

ExtractorFn = Callable[[Path, GraphSnapshot], ExtractionResult]


def augment(repo_root: Path, extractors: list[tuple[str, ExtractorFn]]) -> dict:
    """Run extractors, dedupe, write graph.augmented.json + manifest. Return manifest."""
    graph = GraphSnapshot.load(repo_root)
    nodes_by_id: dict[str, dict] = {}
    edges: list[dict] = []
    edge_keys: set[tuple[str, str, str]] = set()
    failures: list[str] = []
    files_skipped: list[str] = []

    for name, fn in extractors:
        try:
            result = fn(repo_root, graph)
        except Exception as exc:  # noqa: BLE001 — extractor isolation by design
            failures.append(f"{name}: {exc!r}")
            continue
        for node in result.nodes:
            nodes_by_id.setdefault(node.id, _node_to_dict(node))
        for edge in result.edges:
            key = (edge.source, edge.target, edge.relation)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append(_edge_to_dict(edge))
        failures.extend(result.failures)
        files_skipped.extend(result.files_skipped)

    out_path = repo_root / "graphify" / "graph.augmented.json"
    out_path.write_text(
        json.dumps(
            {"nodes": list(nodes_by_id.values()), "links": edges},
            indent=2,
            sort_keys=True,
        )
    )

    manifest = {
        "extension": EXTENSION_TAG,
        "extractors": [name for name, _ in extractors],
        "nodes_emitted": len(nodes_by_id),
        "edges_emitted": len(edges),
        "files_skipped": sorted(set(files_skipped)),
        "failures": failures,
    }
    (repo_root / "graphify" / "graph.augmented.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True)
    )
    return manifest


def _node_to_dict(node: ExtractedNode) -> dict:
    return {
        "id": node.id,
        "label": node.label,
        "file_type": node.file_type,
        "source_file": node.source_file,
        "source_location": node.source_location,
        "extension": EXTENSION_TAG,
        "extractor": node.extractor,
    }


def _edge_to_dict(edge: ExtractedEdge) -> dict:
    return {
        "source": edge.source,
        "target": edge.target,
        "relation": edge.relation,
        "confidence": edge.confidence,
        "confidence_score": edge.confidence_score,
        "source_file": edge.source_file,
        "source_location": edge.source_location,
        "extension": EXTENSION_TAG,
        "extractor": edge.extractor,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_augmenter.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/augmenter.py backend/tests/integrity/plugins/graph_extension/test_augmenter.py
git commit -m "feat(integrity): add augmenter orchestrator with dedupe + manifest"
```

---

## Task 5: AST helpers shared by FastAPI + intra-file extractors

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/extractors/__init__.py`
- Create: `backend/app/integrity/plugins/graph_extension/extractors/_ast_helpers.py`
- Create: `backend/tests/integrity/plugins/graph_extension/test_ast_helpers.py`

- [ ] **Step 1: Write failing tests for helpers**

`backend/tests/integrity/plugins/graph_extension/test_ast_helpers.py`:

```python
from __future__ import annotations
import ast

from backend.app.integrity.plugins.graph_extension.extractors._ast_helpers import (
    extract_kw_str,
    name_of,
)


def test_name_of_simple_name() -> None:
    tree = ast.parse("foo")
    assert name_of(tree.body[0].value) == "foo"


def test_name_of_attribute() -> None:
    tree = ast.parse("router.get")
    assert name_of(tree.body[0].value) == "router.get"


def test_name_of_returns_none_for_subscript() -> None:
    tree = ast.parse("Components[k]")
    assert name_of(tree.body[0].value) is None


def test_extract_kw_str_finds_string_kwarg() -> None:
    tree = ast.parse("APIRouter(prefix='/foo', tags=['x'])")
    call = tree.body[0].value
    assert extract_kw_str(call, "prefix") == "/foo"


def test_extract_kw_str_returns_none_when_missing() -> None:
    tree = ast.parse("APIRouter()")
    call = tree.body[0].value
    assert extract_kw_str(call, "prefix") is None


def test_extract_kw_str_returns_none_for_non_string() -> None:
    tree = ast.parse("APIRouter(prefix=variable)")
    call = tree.body[0].value
    assert extract_kw_str(call, "prefix") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_ast_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement helpers**

`backend/app/integrity/plugins/graph_extension/extractors/__init__.py`:

```python
"""Plugin A extractors: fastapi_routes, intra_file_calls, jsx_usage."""
```

`backend/app/integrity/plugins/graph_extension/extractors/_ast_helpers.py`:

```python
from __future__ import annotations

import ast


def name_of(node: ast.AST | None) -> str | None:
    """Resolve `Name` or dotted `Attribute` chains to a string. Else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = name_of(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def extract_kw_str(call: ast.Call, key: str) -> str | None:
    """Return string value of `key=` kwarg, or None if missing/non-string."""
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_ast_helpers.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/ backend/tests/integrity/plugins/graph_extension/test_ast_helpers.py
git commit -m "feat(integrity): add AST helper utilities"
```

---

## Task 6: FastAPI extractor — single decorator + endpoint pass

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/extractors/fastapi_routes.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/__init__.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/basic_router.py`
- Create: `backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py`

- [ ] **Step 1: Create fixture file**

`backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/__init__.py`: empty.

`backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/basic_router.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/items")


@router.get("/list")
def list_items():
    return []


@router.post("/create")
def create_item(payload: dict):
    return payload


@router.delete("/{item_id}")
async def delete_item(item_id: str):
    return None
```

- [ ] **Step 2: Write failing test for basic decorator extraction**

`backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_extension.extractors import fastapi_routes
from backend.app.integrity.schema import GraphSnapshot

FIXTURES = Path(__file__).parent / "fixtures" / "fastapi_app"


@pytest.fixture
def empty_graph() -> GraphSnapshot:
    return GraphSnapshot(nodes=[], links=[])


def _build_repo(tmp_path: Path, fixture: str) -> Path:
    """Mirror `backend/app/api/<fixture>` under tmp_path."""
    api = tmp_path / "backend" / "app" / "api"
    api.mkdir(parents=True)
    (api / fixture).write_text((FIXTURES / fixture).read_text())
    return tmp_path


def test_basic_router_emits_three_routes(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo(tmp_path, "basic_router.py")
    result = fastapi_routes.extract(repo, empty_graph)

    route_ids = sorted(n.id for n in result.nodes)
    assert route_ids == [
        "route::DELETE::/items/{item_id}",
        "route::GET::/items/list",
        "route::POST::/items/create",
    ]
    # Each route has a routes_to edge
    relations = {(e.source, e.relation) for e in result.edges}
    assert ("route::GET::/items/list", "routes_to") in relations


def test_basic_router_edges_target_handler_function_names(
    tmp_path: Path, empty_graph: GraphSnapshot
) -> None:
    repo = _build_repo(tmp_path, "basic_router.py")
    result = fastapi_routes.extract(repo, empty_graph)

    targets = {e.target for e in result.edges}
    # Target id is "<file_stem>_<function_name>" matching graphify's scheme
    assert "basic_router_list_items" in targets
    assert "basic_router_create_item" in targets
    assert "basic_router_delete_item" in targets
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named '...fastapi_routes'`

- [ ] **Step 4: Implement minimal extractor (single-decorator only)**

`backend/app/integrity/plugins/graph_extension/extractors/fastapi_routes.py`:

```python
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from ...schema import GraphSnapshot  # type: ignore[no-redef]
from ..schema import ExtractedEdge, ExtractedNode, ExtractionResult
from ._ast_helpers import extract_kw_str, name_of

ROUTE_DECORATORS = {"get", "post", "put", "delete", "patch", "websocket"}


@dataclass
class RouterMap:
    """router-variable-name → declared prefix; composition tracks include_router."""

    prefixes: dict[str, str] = field(default_factory=dict)
    composition: list[tuple[str, str, str]] = field(default_factory=list)

    def resolve(self) -> dict[str, str]:
        """Walk composition transitively to compute final prefix per router."""
        resolved = dict(self.prefixes)
        # BFS across composition edges
        changed = True
        while changed:
            changed = False
            for parent, child, added in self.composition:
                parent_prefix = resolved.get(parent, "")
                child_prefix = self.prefixes.get(child, "")
                full = parent_prefix + added + child_prefix
                if resolved.get(child) != full:
                    resolved[child] = full
                    changed = True
        return resolved


def extract(repo_root: Path, graph: GraphSnapshot) -> ExtractionResult:
    api_dir = repo_root / "backend" / "app" / "api"
    if not api_dir.exists():
        return ExtractionResult()

    py_files = sorted(api_dir.rglob("*.py"))
    main_py = repo_root / "backend" / "app" / "main.py"
    topology_files = list(py_files)
    if main_py.exists():
        topology_files.append(main_py)

    router_map = RouterMap()
    failures: list[str] = []

    for path in topology_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            failures.append(f"{path}: {exc}")
            continue
        _collect_router_topology(tree, router_map)

    resolved = router_map.resolve()

    nodes: list[ExtractedNode] = []
    edges: list[ExtractedEdge] = []
    seen_route_ids: set[str] = set()

    for path in py_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = str(path.relative_to(repo_root))
        stem = path.stem
        n, e = _walk_endpoints(tree, rel, stem, resolved, seen_route_ids)
        nodes.extend(n)
        edges.extend(e)

    return ExtractionResult(nodes=nodes, edges=edges, failures=failures)


def _collect_router_topology(tree: ast.AST, router_map: RouterMap) -> None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and name_of(node.value.func) == "APIRouter"
        ):
            router_map.prefixes[node.targets[0].id] = extract_kw_str(node.value, "prefix") or ""

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            parent = name_of(node.func.value)
            child = name_of(node.args[0])
            if parent and child:
                added = extract_kw_str(node, "prefix") or ""
                router_map.composition.append((parent, child, added))


def _walk_endpoints(
    tree: ast.AST,
    rel_path: str,
    stem: str,
    resolved: dict[str, str],
    seen_route_ids: set[str],
) -> tuple[list[ExtractedNode], list[ExtractedEdge]]:
    nodes: list[ExtractedNode] = []
    edges: list[ExtractedEdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            for method, route_path in _routes_from_decorator(dec, resolved):
                route_id = f"route::{method}::{route_path}"
                if route_id not in seen_route_ids:
                    seen_route_ids.add(route_id)
                    nodes.append(
                        ExtractedNode(
                            id=route_id,
                            label=f"{method} {route_path}",
                            file_type="route",
                            source_file=rel_path,
                            source_location=node.lineno,
                            extractor="fastapi_routes",
                        )
                    )
                edges.append(
                    ExtractedEdge(
                        source=route_id,
                        target=f"{stem}_{node.name}",
                        relation="routes_to",
                        source_file=rel_path,
                        source_location=node.lineno,
                        extractor="fastapi_routes",
                    )
                )
    return nodes, edges


def _routes_from_decorator(
    dec: ast.expr, resolved: dict[str, str]
) -> list[tuple[str, str]]:
    """Return [(METHOD, full_path), ...] from one decorator. Empty if not a route."""
    if not isinstance(dec, ast.Call):
        return []
    if not isinstance(dec.func, ast.Attribute):
        return []
    router_name = name_of(dec.func.value)
    if not router_name:
        return []
    method = dec.func.attr
    prefix = resolved.get(router_name, "")
    if method.lower() in ROUTE_DECORATORS:
        path = _first_str_arg(dec) or ""
        return [(method.upper(), prefix + path)]
    return []


def _first_str_arg(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/fastapi_routes.py backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/ backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py
git commit -m "feat(integrity): extract basic FastAPI route decorators"
```

---

## Task 7: FastAPI extractor — api_route + add_api_route + composed routers

**Files:**
- Modify: `backend/app/integrity/plugins/graph_extension/extractors/fastapi_routes.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/api_route_methods.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/composed_router.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/main_with_include.py`
- Modify: `backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py`

- [ ] **Step 1: Create fixtures**

`backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/api_route_methods.py`:

```python
from fastapi import APIRouter, FastAPI

router = APIRouter(prefix="/multi")
app = FastAPI()


@router.api_route("/both", methods=["GET", "POST"])
def both_methods():
    return {}


def programmatic_handler():
    return {}


app.add_api_route("/programmatic", programmatic_handler, methods=["PUT"])
```

`backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/composed_router.py`:

```python
from fastapi import APIRouter

inner = APIRouter(prefix="/inner")


@inner.get("/leaf")
def leaf():
    return {}
```

`backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/main_with_include.py`:

```python
from fastapi import FastAPI

from . import composed_router

app = FastAPI()
app.include_router(composed_router.inner, prefix="/v1")
```

- [ ] **Step 2: Add failing tests for the new fixtures**

Append to `backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py`:

```python
def _build_repo_multi(tmp_path: Path, fixtures: list[str]) -> Path:
    api = tmp_path / "backend" / "app" / "api"
    api.mkdir(parents=True)
    (api / "__init__.py").write_text("")
    for f in fixtures:
        (api / f).write_text((FIXTURES / f).read_text())
    return tmp_path


def test_api_route_fans_out_methods(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo_multi(tmp_path, ["api_route_methods.py"])
    result = fastapi_routes.extract(repo, empty_graph)

    ids = {n.id for n in result.nodes}
    assert "route::GET::/multi/both" in ids
    assert "route::POST::/multi/both" in ids


def test_add_api_route_emits_route(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo_multi(tmp_path, ["api_route_methods.py"])
    result = fastapi_routes.extract(repo, empty_graph)

    ids = {n.id for n in result.nodes}
    assert "route::PUT::/programmatic" in ids


def test_include_router_composes_prefix(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    # main.py lives at backend/app/main.py — needs special placement
    repo = tmp_path
    (repo / "backend" / "app" / "api").mkdir(parents=True)
    (repo / "backend" / "app" / "api" / "__init__.py").write_text("")
    (repo / "backend" / "app" / "api" / "composed_router.py").write_text(
        (FIXTURES / "composed_router.py").read_text()
    )
    (repo / "backend" / "app" / "main.py").write_text(
        (FIXTURES / "main_with_include.py").read_text()
    )

    result = fastapi_routes.extract(repo, empty_graph)
    ids = {n.id for n in result.nodes}
    assert "route::GET::/v1/inner/leaf" in ids
```

- [ ] **Step 3: Run new tests to verify they fail**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py -v`
Expected: 3 new tests FAIL (api_route, add_api_route, include_router not yet handled)

- [ ] **Step 4: Extend extractor for `api_route` + `add_api_route`**

Replace `_routes_from_decorator` in `fastapi_routes.py`:

```python
def _routes_from_decorator(
    dec: ast.expr, resolved: dict[str, str]
) -> list[tuple[str, str]]:
    if not isinstance(dec, ast.Call):
        return []
    if not isinstance(dec.func, ast.Attribute):
        return []
    router_name = name_of(dec.func.value)
    if not router_name:
        return []
    method = dec.func.attr
    prefix = resolved.get(router_name, "")
    path = _first_str_arg(dec) or ""

    if method.lower() in ROUTE_DECORATORS:
        return [(method.upper(), prefix + path)]
    if method == "api_route":
        methods = _extract_methods_kw(dec)
        return [(m.upper(), prefix + path) for m in methods]
    return []


def _extract_methods_kw(call: ast.Call) -> list[str]:
    for kw in call.keywords:
        if kw.arg == "methods" and isinstance(kw.value, ast.List):
            out: list[str] = []
            for elt in kw.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.append(elt.value)
            return out
    return []
```

Add a new top-level scan for `app.add_api_route(...)` calls. In `extract()`, after the endpoint-pass loop, append:

```python
    # Programmatic add_api_route calls
    for path in py_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = str(path.relative_to(repo_root))
        stem = path.stem
        n, e = _walk_add_api_route(tree, rel, stem, resolved, seen_route_ids)
        nodes.extend(n)
        edges.extend(e)
```

And add the helper:

```python
def _walk_add_api_route(
    tree: ast.AST,
    rel_path: str,
    stem: str,
    resolved: dict[str, str],
    seen_route_ids: set[str],
) -> tuple[list[ExtractedNode], list[ExtractedEdge]]:
    nodes: list[ExtractedNode] = []
    edges: list[ExtractedEdge] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_api_route"
            and len(node.args) >= 2
        ):
            continue
        path_arg = node.args[0]
        if not (isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str)):
            continue
        url = path_arg.value
        handler_name = name_of(node.args[1])
        if not handler_name:
            continue
        for method in _extract_methods_kw(node):
            route_id = f"route::{method.upper()}::{url}"
            if route_id not in seen_route_ids:
                seen_route_ids.add(route_id)
                nodes.append(
                    ExtractedNode(
                        id=route_id,
                        label=f"{method.upper()} {url}",
                        file_type="route",
                        source_file=rel_path,
                        source_location=node.lineno,
                        extractor="fastapi_routes",
                    )
                )
            target = handler_name.split(".")[-1]
            edges.append(
                ExtractedEdge(
                    source=route_id,
                    target=f"{stem}_{target}",
                    relation="routes_to",
                    source_file=rel_path,
                    source_location=node.lineno,
                    extractor="fastapi_routes",
                )
            )
    return nodes, edges
```

The composition (`include_router`) test should already pass because Task 6's implementation already collects `composition` and `resolve()` walks it. If the test still fails, ensure topology pass also visits `main.py` (already wired via `topology_files`).

- [ ] **Step 5: Run all FastAPI tests**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/fastapi_routes.py backend/tests/integrity/plugins/graph_extension/fixtures/fastapi_app/ backend/tests/integrity/plugins/graph_extension/test_fastapi_routes.py
git commit -m "feat(integrity): extract api_route, add_api_route, composed router prefixes"
```

---

## Task 8: Intra-file calls extractor

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/extractors/intra_file_calls.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/__init__.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/two_funcs.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/self_method.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/decorated_helpers.py`
- Create: `backend/tests/integrity/plugins/graph_extension/test_intra_file_calls.py`

- [ ] **Step 1: Create fixtures**

`backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/__init__.py`: empty.

`backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/two_funcs.py`:

```python
def helper(x):
    return x + 1


def public(value):
    base = helper(value)
    return base * 2


def isolated():
    return 0
```

`backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/self_method.py`:

```python
class Calculator:
    def add(self, a, b):
        return a + b

    def double(self, x):
        return self.add(x, x)
```

`backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/decorated_helpers.py`:

```python
from functools import lru_cache


@lru_cache
def cached_value():
    return 42


def caller():
    return cached_value()
```

- [ ] **Step 2: Write failing test**

`backend/tests/integrity/plugins/graph_extension/test_intra_file_calls.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_extension.extractors import intra_file_calls
from backend.app.integrity.schema import GraphSnapshot

FIXTURES = Path(__file__).parent / "fixtures" / "intra_file"


@pytest.fixture
def empty_graph() -> GraphSnapshot:
    return GraphSnapshot(nodes=[], links=[])


def _scan(tmp_path: Path, fixture: str, empty_graph: GraphSnapshot):
    py = tmp_path / "backend" / "app" / "module.py"
    py.parent.mkdir(parents=True)
    py.write_text((FIXTURES / fixture).read_text())
    return intra_file_calls.extract(tmp_path, empty_graph)


def test_module_level_call_emits_calls_edge(tmp_path, empty_graph: GraphSnapshot) -> None:
    result = _scan(tmp_path, "two_funcs.py", empty_graph)
    edges = {(e.source, e.target, e.relation) for e in result.edges}
    assert ("module_public", "module_helper", "calls") in edges


def test_isolated_function_emits_no_outgoing_calls(tmp_path, empty_graph: GraphSnapshot) -> None:
    result = _scan(tmp_path, "two_funcs.py", empty_graph)
    sources = {e.source for e in result.edges}
    assert "module_isolated" not in sources


def test_self_method_call_emits_class_method_edge(tmp_path, empty_graph: GraphSnapshot) -> None:
    result = _scan(tmp_path, "self_method.py", empty_graph)
    edges = {(e.source, e.target, e.relation) for e in result.edges}
    # self.add() inside double() — caller is module_double, target is module_add
    assert ("module_double", "module_add", "calls") in edges


def test_decorated_helper_call_resolves_to_def(tmp_path, empty_graph: GraphSnapshot) -> None:
    result = _scan(tmp_path, "decorated_helpers.py", empty_graph)
    edges = {(e.source, e.target, e.relation) for e in result.edges}
    assert ("module_caller", "module_cached_value", "calls") in edges
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_intra_file_calls.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement extractor**

`backend/app/integrity/plugins/graph_extension/extractors/intra_file_calls.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

from ...schema import GraphSnapshot
from ..schema import ExtractedEdge, ExtractionResult


def extract(repo_root: Path, graph: GraphSnapshot) -> ExtractionResult:
    failures: list[str] = []
    edges: list[ExtractedEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()

    backend_root = repo_root / "backend" / "app"
    if not backend_root.exists():
        return ExtractionResult()

    for path in sorted(backend_root.rglob("*.py")):
        if any(part.startswith(("__pycache__", ".")) for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            failures.append(f"{path}: {exc}")
            continue

        rel = str(path.relative_to(repo_root))
        stem = path.stem
        local_defs = _collect_local_defs(tree)
        for caller_name, call_node, _ in _iter_calls_with_caller(tree):
            target = _resolve_callee(call_node, local_defs)
            if target is None:
                continue
            edge_key = (f"{stem}_{caller_name}", f"{stem}_{target}", "calls")
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append(
                ExtractedEdge(
                    source=f"{stem}_{caller_name}",
                    target=f"{stem}_{target}",
                    relation="calls",
                    source_file=rel,
                    source_location=call_node.lineno,
                    extractor="intra_file_calls",
                )
            )

    return ExtractionResult(edges=edges, failures=failures)


def _collect_local_defs(tree: ast.AST) -> set[str]:
    """Module-level def/async def/class names + class-method names."""
    out: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        if isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(inner.name)
    return out


def _iter_calls_with_caller(tree: ast.AST):
    """Yield (caller_name, Call node, parent_class_or_None) for every Call."""
    for top in ast.iter_child_nodes(tree):
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(top):
                if isinstance(child, ast.Call):
                    yield top.name, child, None
        elif isinstance(top, ast.ClassDef):
            for inner in top.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(inner):
                        if isinstance(child, ast.Call):
                            yield inner.name, child, top.name


def _resolve_callee(call: ast.Call, local_defs: set[str]) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id if func.id in local_defs else None
    if isinstance(func, ast.Attribute):
        # self.method() — only handle when receiver is `self`
        if isinstance(func.value, ast.Name) and func.value.id == "self":
            return func.attr if func.attr in local_defs else None
    return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_intra_file_calls.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/intra_file_calls.py backend/tests/integrity/plugins/graph_extension/fixtures/intra_file/ backend/tests/integrity/plugins/graph_extension/test_intra_file_calls.py
git commit -m "feat(integrity): extract intra-file Python calls"
```

---

## Task 9: JSX Node helper — direct usage + HOC + render-prop

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs`
- Create: `backend/app/integrity/plugins/graph_extension/extractors/_node_helper/package.json`
- Create: `backend/app/integrity/plugins/graph_extension/extractors/_node_helper/.gitignore`

- [ ] **Step 1: Create pinned package.json**

`backend/app/integrity/plugins/graph_extension/extractors/_node_helper/package.json`:

```json
{
  "name": "graph-extension-jsx-helper",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "description": "Node helper that parses JSX/TSX with @babel/parser and emits component-usage edges as JSON.",
  "dependencies": {
    "@babel/parser": "7.25.0",
    "@babel/traverse": "7.25.0"
  }
}
```

`backend/app/integrity/plugins/graph_extension/extractors/_node_helper/.gitignore`:

```
node_modules/
package-lock.json
```

- [ ] **Step 2: Install pinned deps**

```bash
cd /Users/jay/Developer/claude-code-agent/backend/app/integrity/plugins/graph_extension/extractors/_node_helper && npm install
```

Expected: `node_modules/@babel/parser` and `node_modules/@babel/traverse` exist.

- [ ] **Step 3: Write the helper**

`backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs`:

```javascript
#!/usr/bin/env node
/**
 * Reads a JSON list of file paths from stdin.
 * For each, parses with @babel/parser (jsx + typescript plugins) and emits
 * one record per usage edge. Output: JSON to stdout.
 *
 * Schema:
 *   [{file, edges: [{source, target, kind, line}], errors: [string]}]
 */
import { readFileSync } from 'node:fs';
import { resolve, dirname, basename, extname } from 'node:path';
import { parse } from '@babel/parser';
import traverseModule from '@babel/traverse';

const traverse = traverseModule.default ?? traverseModule;

const HOC_NAMES = new Set([
  'withRouter', 'withTranslation', 'withStyles', 'withTheme', 'connect', 'observer', 'memo', 'forwardRef',
]);

function readStdin() {
  return readFileSync(0, 'utf-8');
}

function parseFile(filePath) {
  const code = readFileSync(filePath, 'utf-8');
  return parse(code, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript', 'decorators-legacy'],
    errorRecovery: true,
  });
}

function fileToComponentName(filePath) {
  const base = basename(filePath, extname(filePath));
  return base;
}

function getEnclosingDeclName(path) {
  let cur = path.parentPath;
  while (cur) {
    if (cur.isFunctionDeclaration() && cur.node.id) return cur.node.id.name;
    if (cur.isVariableDeclarator() && cur.node.id?.name) return cur.node.id.name;
    if (cur.isClassDeclaration() && cur.node.id) return cur.node.id.name;
    if (cur.isExportDefaultDeclaration()) return 'default';
    cur = cur.parentPath;
  }
  return null;
}

function jsxOpeningName(node) {
  // <Foo /> → 'Foo'   <Foo.Bar /> → 'Foo.Bar'
  let n = node.name;
  if (n.type === 'JSXIdentifier') return n.name;
  if (n.type === 'JSXMemberExpression') {
    const parts = [];
    while (n.type === 'JSXMemberExpression') {
      parts.unshift(n.property.name);
      n = n.object;
    }
    if (n.type === 'JSXIdentifier') parts.unshift(n.name);
    return parts.join('.');
  }
  return null;
}

function isComponent(name) {
  if (!name) return false;
  // Components start with uppercase or contain a `.` (member exprs)
  return /^[A-Z]/.test(name.split('.')[0]);
}

function unwrapHOC(node) {
  // withFoo(MyComp) → MyComp
  // connect(state)(MyComp) → MyComp
  // memo(forwardRef(MyComp)) → MyComp
  let cur = node;
  while (cur && cur.type === 'CallExpression') {
    const callee = cur.callee;
    if (callee.type === 'Identifier' && HOC_NAMES.has(callee.name)) {
      // find first identifier-like arg
      const arg = cur.arguments.find(a => a.type === 'Identifier' || a.type === 'CallExpression');
      if (!arg) return null;
      if (arg.type === 'Identifier') return arg.name;
      cur = arg;
      continue;
    }
    if (callee.type === 'CallExpression') {
      // connect(state)(MyComp) — callee itself is a call returning HOC
      const arg = cur.arguments.find(a => a.type === 'Identifier');
      return arg ? arg.name : null;
    }
    return null;
  }
  return null;
}

function extractEdges(filePath) {
  const out = { file: filePath, edges: [], errors: [] };
  let ast;
  try {
    ast = parseFile(filePath);
  } catch (e) {
    out.errors.push(String(e.message ?? e));
    return out;
  }

  const fileComp = fileToComponentName(filePath);

  traverse(ast, {
    JSXOpeningElement(path) {
      const target = jsxOpeningName(path.node);
      if (!isComponent(target)) return;
      const enc = getEnclosingDeclName(path) ?? fileComp;
      out.edges.push({
        source: enc,
        target: target.split('.')[0],
        kind: 'direct',
        line: path.node.loc?.start?.line ?? null,
      });
    },
    ExportDefaultDeclaration(path) {
      const decl = path.node.declaration;
      if (decl?.type === 'CallExpression') {
        const inner = unwrapHOC(decl);
        if (inner) {
          out.edges.push({
            source: 'default',
            target: inner,
            kind: 'hoc',
            line: path.node.loc?.start?.line ?? null,
          });
        }
      }
    },
  });

  return out;
}

function main() {
  const raw = readStdin();
  let files;
  try {
    files = JSON.parse(raw);
  } catch (e) {
    process.stderr.write(`bad stdin JSON: ${e}\n`);
    process.exit(2);
  }
  const out = files.map(extractEdges);
  process.stdout.write(JSON.stringify(out));
}

main();
```

- [ ] **Step 4: Smoke-test the Node helper directly**

```bash
cd /Users/jay/Developer/claude-code-agent && mkdir -p /tmp/jsx_smoke && cat > /tmp/jsx_smoke/A.tsx <<'EOF'
import B from './B'
function A() { return <B /> }
export default A
EOF
echo '["/tmp/jsx_smoke/A.tsx"]' | node backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs
```

Expected output (formatted):

```json
[{"file":"/tmp/jsx_smoke/A.tsx","edges":[{"source":"A","target":"B","kind":"direct","line":2}],"errors":[]}]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/_node_helper/
git commit -m "feat(integrity): add Node helper for JSX usage extraction"
```

---

## Task 10: JSX Node helper — lazy imports + render-prop callbacks

**Files:**
- Modify: `backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs`

- [ ] **Step 1: Create lazy + render-prop fixtures + smoke test**

```bash
cat > /tmp/jsx_smoke/Lazy.tsx <<'EOF'
import { lazy } from 'react'
const Heavy = lazy(() => import('./Heavy'))
function Page() { return <Heavy /> }
export default Page
EOF
cat > /tmp/jsx_smoke/Render.tsx <<'EOF'
import Inner from './Inner'
import Outer from './Outer'
function Page() {
  return <Outer render={(x) => <Inner x={x} />} />
}
export default Page
EOF
echo '["/tmp/jsx_smoke/Lazy.tsx","/tmp/jsx_smoke/Render.tsx"]' | node backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs
```

Currently fails to surface `Page → Heavy` (via `lazy(() => import('./Heavy'))`) and `Page → Inner` (render prop already resolved by JSXOpeningElement walk — verify).

- [ ] **Step 2: Add `lazy(() => import('./X'))` handling**

Add this visitor inside `traverse(ast, { ... })` in `parse_jsx.mjs`:

```javascript
    VariableDeclarator(path) {
      const init = path.node.init;
      if (!init || init.type !== 'CallExpression') return;
      if (init.callee.type !== 'Identifier' || init.callee.name !== 'lazy') return;
      const arrow = init.arguments[0];
      if (!arrow || (arrow.type !== 'ArrowFunctionExpression' && arrow.type !== 'FunctionExpression')) return;
      const body = arrow.body;
      const importCall = body.type === 'CallExpression' ? body :
        (body.type === 'BlockStatement' ? null : null);
      if (!importCall || importCall.callee.type !== 'Import') return;
      const arg = importCall.arguments[0];
      if (arg?.type !== 'StringLiteral') return;
      const lazyName = path.node.id?.name;
      if (!lazyName) return;
      const importedBase = arg.value.split('/').pop();
      out.edges.push({
        source: lazyName,
        target: importedBase,
        kind: 'lazy',
        line: path.node.loc?.start?.line ?? null,
      });
    },
```

Render-prop callbacks already work because the inner JSX (`<Inner />`) is a `JSXOpeningElement` and `getEnclosingDeclName` walks up to find the enclosing `Page`. Verify in step 3.

- [ ] **Step 3: Re-run smoke test**

```bash
echo '["/tmp/jsx_smoke/Lazy.tsx","/tmp/jsx_smoke/Render.tsx"]' | node backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs | python3 -m json.tool
```

Expected (key edges present):

```json
[
  {"file": ".../Lazy.tsx", "edges": [
    {"source": "Heavy", "target": "Heavy", "kind": "lazy", "line": 2},
    {"source": "Page", "target": "Heavy", "kind": "direct", "line": 3}
  ], "errors": []},
  {"file": ".../Render.tsx", "edges": [
    {"source": "Page", "target": "Outer", "kind": "direct", "line": 4},
    {"source": "Page", "target": "Inner", "kind": "direct", "line": 4}
  ], "errors": []}
]
```

- [ ] **Step 4: Cleanup**

```bash
rm -rf /tmp/jsx_smoke
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/_node_helper/parse_jsx.mjs
git commit -m "feat(integrity): JSX helper handles lazy imports + render-prop callbacks"
```

---

## Task 11: JSX Python wrapper

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/extractors/jsx_usage.py`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/Direct.tsx`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/HOC.tsx`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/LazyImport.tsx`
- Create: `backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/RenderProp.tsx`
- Create: `backend/tests/integrity/plugins/graph_extension/test_jsx_usage.py`

- [ ] **Step 1: Create fixtures**

`backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/Direct.tsx`:

```tsx
import Inner from './Inner'

export default function Direct() {
  return <Inner />
}
```

`backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/HOC.tsx`:

```tsx
import { connect } from 'react-redux'

function MyComp() { return null }

export default connect(state => state)(MyComp)
```

`backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/LazyImport.tsx`:

```tsx
import { lazy } from 'react'

const Heavy = lazy(() => import('./Heavy'))

export default function Page() {
  return <Heavy />
}
```

`backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/RenderProp.tsx`:

```tsx
import Outer from './Outer'
import Inner from './Inner'

export default function Page() {
  return <Outer render={(x: any) => <Inner x={x} />} />
}
```

- [ ] **Step 2: Write failing test**

`backend/tests/integrity/plugins/graph_extension/test_jsx_usage.py`:

```python
from __future__ import annotations
import shutil
from pathlib import Path

import pytest

from backend.app.integrity.plugins.graph_extension.extractors import jsx_usage
from backend.app.integrity.schema import GraphSnapshot

FIXTURES = Path(__file__).parent / "fixtures" / "jsx_app"


@pytest.fixture
def empty_graph() -> GraphSnapshot:
    return GraphSnapshot(nodes=[], links=[])


def _build_repo(tmp_path: Path, names: list[str]) -> Path:
    src = tmp_path / "frontend" / "src"
    src.mkdir(parents=True)
    for name in names:
        shutil.copy(FIXTURES / name, src / name)
    return tmp_path


def test_direct_component_usage(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo(tmp_path, ["Direct.tsx"])
    result = jsx_usage.extract(repo, empty_graph)
    relations = {(e.source, e.target, e.relation) for e in result.edges}
    assert ("Direct", "Inner", "uses") in relations


def test_hoc_unwrap(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo(tmp_path, ["HOC.tsx"])
    result = jsx_usage.extract(repo, empty_graph)
    targets = {e.target for e in result.edges}
    assert "MyComp" in targets


def test_lazy_import(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo(tmp_path, ["LazyImport.tsx"])
    result = jsx_usage.extract(repo, empty_graph)
    targets = {e.target for e in result.edges}
    assert "Heavy" in targets


def test_render_prop_callback(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    repo = _build_repo(tmp_path, ["RenderProp.tsx"])
    result = jsx_usage.extract(repo, empty_graph)
    targets = {e.target for e in result.edges}
    assert "Inner" in targets
    assert "Outer" in targets


def test_no_frontend_dir_returns_empty(tmp_path: Path, empty_graph: GraphSnapshot) -> None:
    result = jsx_usage.extract(tmp_path, empty_graph)
    assert result.edges == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_jsx_usage.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement Python wrapper**

`backend/app/integrity/plugins/graph_extension/extractors/jsx_usage.py`:

```python
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ...schema import GraphSnapshot
from ..schema import ExtractedEdge, ExtractionResult

HELPER_DIR = Path(__file__).parent / "_node_helper"
HELPER_SCRIPT = HELPER_DIR / "parse_jsx.mjs"


class ExtractorUnavailable(RuntimeError):
    """Raised when Node or @babel/parser is not installed."""


def extract(repo_root: Path, graph: GraphSnapshot) -> ExtractionResult:
    src_dir = repo_root / "frontend" / "src"
    if not src_dir.exists():
        return ExtractionResult()

    files = sorted(
        str(p) for p in src_dir.rglob("*.tsx")
    ) + sorted(
        str(p) for p in src_dir.rglob("*.jsx")
    )
    if not files:
        return ExtractionResult()

    if shutil.which("node") is None:
        return ExtractionResult(failures=["node executable not found on PATH"])
    if not (HELPER_DIR / "node_modules" / "@babel" / "parser").exists():
        return ExtractionResult(
            failures=[
                f"@babel/parser missing — run `npm install` in {HELPER_DIR}"
            ]
        )

    try:
        proc = subprocess.run(
            ["node", str(HELPER_SCRIPT)],
            input=json.dumps(files),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ExtractionResult(failures=["jsx_usage subprocess timed out"])

    if proc.returncode != 0:
        return ExtractionResult(failures=[f"node helper exit {proc.returncode}: {proc.stderr.strip()}"])

    try:
        records = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ExtractionResult(failures=[f"helper output not JSON: {exc}"])

    edges: list[ExtractedEdge] = []
    failures: list[str] = []
    files_skipped: list[str] = []
    edge_keys: set[tuple[str, str, str]] = set()

    for rec in records:
        rel = str(Path(rec["file"]).relative_to(repo_root))
        if rec.get("errors"):
            files_skipped.append(rel)
            failures.extend(f"{rel}: {e}" for e in rec["errors"])
            continue
        for edge in rec.get("edges", []):
            source = edge["source"]
            target = edge["target"]
            key = (source, target, "uses")
            if key in edge_keys or source == target:
                continue
            edge_keys.add(key)
            edges.append(
                ExtractedEdge(
                    source=source,
                    target=target,
                    relation="uses",
                    source_file=rel,
                    source_location=edge.get("line"),
                    extractor="jsx_usage",
                )
            )

    return ExtractionResult(edges=edges, files_skipped=files_skipped, failures=failures)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_jsx_usage.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/extractors/jsx_usage.py backend/tests/integrity/plugins/graph_extension/fixtures/jsx_app/ backend/tests/integrity/plugins/graph_extension/test_jsx_usage.py
git commit -m "feat(integrity): add JSX usage Python wrapper around Node helper"
```

---

## Task 12: Plugin entry + CLI

**Files:**
- Create: `backend/app/integrity/plugins/graph_extension/plugin.py`
- Create: `backend/app/integrity/plugins/graph_extension/cli.py`
- Create: `backend/app/integrity/plugins/graph_extension/__main__.py`
- Create: `backend/tests/integrity/plugins/graph_extension/test_plugin.py`

- [ ] **Step 1: Write failing test for plugin entry**

`backend/tests/integrity/plugins/graph_extension/test_plugin.py`:

```python
from __future__ import annotations
import json
from pathlib import Path

from backend.app.integrity.plugins.graph_extension.plugin import GraphExtensionPlugin
from backend.app.integrity.protocol import IntegrityPlugin, ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _seed_graph(tmp_path: Path) -> GraphSnapshot:
    g = tmp_path / "graphify"
    g.mkdir()
    (g / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))
    return GraphSnapshot.load(tmp_path)


def test_plugin_satisfies_protocol() -> None:
    plugin = GraphExtensionPlugin()
    assert isinstance(plugin, IntegrityPlugin)
    assert plugin.name == "graph_extension"
    assert plugin.version  # non-empty


def test_plugin_scan_writes_augmented_graph(tmp_path: Path) -> None:
    graph = _seed_graph(tmp_path)
    ctx = ScanContext(repo_root=tmp_path, graph=graph)

    result = GraphExtensionPlugin().scan(ctx)

    aug = tmp_path / "graphify" / "graph.augmented.json"
    assert aug.exists()
    assert result.plugin_name == "graph_extension"
    assert any(str(a).endswith("graph.augmented.json") for a in result.artifacts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_plugin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named '...plugin'`

- [ ] **Step 3: Implement plugin + CLI**

`backend/app/integrity/plugins/graph_extension/plugin.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from ...protocol import ScanContext, ScanResult
from .augmenter import augment
from .extractors import fastapi_routes, intra_file_calls, jsx_usage


@dataclass
class GraphExtensionPlugin:
    name: str = "graph_extension"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ()
    paths: tuple[str, ...] = field(
        default=(
            "backend/app/api/**/*.py",
            "backend/app/main.py",
            "backend/app/**/*.py",
            "frontend/src/**/*.tsx",
            "frontend/src/**/*.jsx",
        )
    )

    def scan(self, ctx: ScanContext) -> ScanResult:
        manifest = augment(
            ctx.repo_root,
            extractors=[
                ("fastapi_routes", fastapi_routes.extract),
                ("intra_file_calls", intra_file_calls.extract),
                ("jsx_usage", jsx_usage.extract),
            ],
        )
        artifacts = [
            ctx.repo_root / "graphify" / "graph.augmented.json",
            ctx.repo_root / "graphify" / "graph.augmented.manifest.json",
        ]
        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            artifacts=artifacts,
            failures=manifest.get("failures", []),
        )
```

`backend/app/integrity/plugins/graph_extension/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .plugin import GraphExtensionPlugin
from ...protocol import ScanContext
from ...schema import GraphSnapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run plugin A — graph augmentation.")
    parser.add_argument(
        "--repo-root",
        default=".",
        type=Path,
        help="Path to the repository root (default: cwd).",
    )
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()

    graph = GraphSnapshot.load(repo)
    ctx = ScanContext(repo_root=repo, graph=graph)
    result = GraphExtensionPlugin().scan(ctx)

    summary = {
        "plugin": result.plugin_name,
        "version": result.plugin_version,
        "artifacts": [str(a) for a in result.artifacts],
        "failures": result.failures,
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if not result.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

`backend/app/integrity/plugins/graph_extension/__main__.py`:

```python
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jay/Developer/claude-code-agent && uv run python -m pytest backend/tests/integrity/plugins/graph_extension/test_plugin.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Verify CLI module-mode entry**

```bash
cd /Users/jay/Developer/claude-code-agent && uv run python -m backend.app.integrity.plugins.graph_extension --repo-root .
```

Expected: prints JSON summary, exits 0 (assuming graphify/graph.json exists; otherwise FileNotFoundError — that's expected on a fresh checkout, just confirms the entry-point wiring).

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrity/plugins/graph_extension/plugin.py backend/app/integrity/plugins/graph_extension/cli.py backend/app/integrity/plugins/graph_extension/__main__.py backend/tests/integrity/plugins/graph_extension/test_plugin.py
git commit -m "feat(integrity): wire plugin A entry + CLI"
```

---

## Task 13: Makefile target + run all integrity tests

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add `integrity-augment` target**

Append to `/Users/jay/Developer/claude-code-agent/Makefile`:

```makefile

# Integrity (self-maintaining graph)
.PHONY: integrity-augment integrity-test
integrity-augment:
	cd backend && uv run python -m app.integrity.plugins.graph_extension --repo-root ..

integrity-test:
	cd backend && uv run python -m pytest tests/integrity/ -v
```

Update the `.PHONY` line at the top of the Makefile to include `integrity-augment integrity-test`.

- [ ] **Step 2: Run full integrity test suite**

```bash
cd /Users/jay/Developer/claude-code-agent && make integrity-test
```

Expected: ALL tests pass (engine: 2; schema: 2; ast_helpers: 6; augmenter: 4; fastapi_routes: 5; intra_file_calls: 4; jsx_usage: 5; plugin: 2 → 30 total).

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat(integrity): add make integrity-augment + integrity-test targets"
```

---

## Task 14: Acceptance gate — run on real repo + verify FP rate

**Files:**
- (No code changes; verification only.)

- [ ] **Step 1: Capture baseline FP rate (before augmentation)**

```bash
cd /Users/jay/Developer/claude-code-agent && rm -f graphify/graph.augmented.json && uv run python scripts/verify_orphans.py | tail -10
```

Expected: prints baseline summary, e.g. "Truly dead: 63 / 100 (37.0%)" — record the backend and frontend numbers in the commit message of step 4.

- [ ] **Step 2: Run augmenter on real repo**

```bash
cd /Users/jay/Developer/claude-code-agent && make integrity-augment
```

Expected: writes `graphify/graph.augmented.json` and `graphify/graph.augmented.manifest.json`. Manifest reports nonzero `nodes_emitted` and `edges_emitted`. No `failures` in the manifest (or only the documented `node executable not found` / `@babel/parser missing` if those are missing — must be absent for the gate).

- [ ] **Step 3: Re-run FP-rate audit**

```bash
cd /Users/jay/Developer/claude-code-agent && uv run python scripts/verify_orphans.py | tail -20
```

Expected (acceptance gate α): backend FP rate <15%, frontend FP rate <30%. Record both numbers.

- [ ] **Step 4: If gate fails, diagnose**

If backend FP rate ≥15%:
1. Inspect a handful of remaining false-positive backend orphans from the audit output
2. Confirm whether they're FastAPI routes the extractor missed (check decorator shape — is it `@router.get` or some custom pattern?)
3. If a new pattern surfaces, add a fixture + test (back in Task 7) and a corresponding extension to `_routes_from_decorator`
4. Re-run from Step 2

If frontend FP rate ≥30%:
1. Inspect remaining frontend orphans
2. Confirm whether they're missed JSX usages (HOC variant not covered? dynamic component lookup?)
3. Add fixture + test (back in Task 11) and extend `parse_jsx.mjs`
4. Re-run from Step 2

- [ ] **Step 5: Commit gate result**

```bash
git add graphify/graph.augmented.json graphify/graph.augmented.manifest.json
git commit -m "chore(integrity): plugin A passes gate α — backend FP <NN>% / frontend FP <NN>%"
```

(Substitute the actual measured numbers from Step 3.)

---

## Self-review notes

**Spec coverage:**

| Spec section | Covered by |
|---|---|
| §3 Operating model — `graph.augmented.json` separate output | Task 4 (augmenter), Task 11 (jsx wrapper writes via augmenter) |
| §3 Operating model — `extension: "cca-v1"` provenance | Task 4 (`_node_to_dict`, `_edge_to_dict`) |
| §3 Read-precedence contract | Task 3 (`verify_orphans.py` patched) |
| §4 Internal structure | Task 5 (helpers), Tasks 6-11 (extractors), Task 12 (plugin/CLI) |
| §5.1 FastAPI extractor — basic decorators | Task 6 |
| §5.1 FastAPI extractor — `api_route`, `add_api_route`, `include_router` | Task 7 |
| §5.2 Intra-file calls — module-level + self-method + decorated | Task 8 |
| §5.3 JSX — direct, render-prop, HOC, lazy, dynamic | Tasks 9-11 (dynamic-component covered by JSXMemberExpression handling in Task 9) |
| §6 Provenance markers + idempotent re-runs | Task 4 (idempotency test) |
| §7 Triggers (make + module CLI + plugin) | Tasks 12-13 (cron wired by ops, not plan) |
| §8 Error handling — extractor isolation, parse-failure recording | Task 4 (failure capture), Tasks 6/8/11 (skip-on-error) |
| §9 Testing acceptance gates | Tasks 6-11 fixtures, Task 14 end-to-end |
| §10 Operational defaults — output paths | Task 4 |
| §11 Open questions | Deferred — flagged for v1.1 in spec |

**Type consistency:** `ExtractedNode`/`ExtractedEdge`/`ExtractionResult` defined in Task 3, used unchanged in Tasks 4, 6, 7, 8, 11. `augment()` signature in Task 4 matches the call in Task 12. `extract()` extractor signature `(Path, GraphSnapshot) -> ExtractionResult` consistent across Tasks 6, 8, 11.

**Placeholder scan:** None — all code is concrete and runnable.

---
