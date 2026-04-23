# Research Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular research coordinator tool (`research`, `research_start`, `research_get`) that gives the main agent access to papers, code examples, and web content via isolated sub-modules.

**Architecture:** RoutingAgent (haiku LLM) decides which of three source modules to run and allocates a single `budget_tokens` parameter across them. Modules run in parallel when safe. SynthesisAgent (haiku LLM) merges outputs into a structured result. Async variant stores results in a thread-safe JobRegistry.

**Tech Stack:** Python 3.12, anthropic SDK (direct, not via harness clients), httpx, subprocess for `gh` CLI, existing `ToolDispatcher` + `StreamEvent` + trace bus patterns.

---

## File Map

| File | Role |
|------|------|
| `backend/app/harness/research/__init__.py` | Package marker |
| `backend/app/harness/research/types.py` | All dataclasses: PaperFinding, CodeExample, WebPage, PapersResult, CodeResult, WebResult, ResearchResult, RoutePlan |
| `backend/app/harness/research/jobs.py` | JobRegistry singleton — thread-safe dict, TTL expiry |
| `backend/app/harness/research/modules/papers.py` | PapersModule — HF Papers + Semantic Scholar + ArXiv |
| `backend/app/harness/research/modules/code.py` | CodeModule — gh CLI wrapper |
| `backend/app/harness/research/modules/web.py` | WebModule — httpx fetch + strip HTML |
| `backend/app/harness/research/router.py` | RoutingAgent — one haiku LLM call → RoutePlan |
| `backend/app/harness/research/synthesis.py` | SynthesisAgent — one haiku LLM call → ResearchResult |
| `backend/app/harness/research/tool.py` | ResearchTool — orchestrates everything; exposes execute(), start(), get() and the 3 ToolSchema defs |
| `backend/app/harness/research/tests/test_types.py` | Type round-trip tests |
| `backend/app/harness/research/tests/test_jobs.py` | JobRegistry tests |
| `backend/app/harness/research/tests/test_papers.py` | PapersModule tests (mock httpx) |
| `backend/app/harness/research/tests/test_code.py` | CodeModule tests (mock subprocess) |
| `backend/app/harness/research/tests/test_web.py` | WebModule tests (mock httpx) |
| `backend/app/harness/research/tests/test_router.py` | RoutingAgent tests (mock anthropic) |
| `backend/app/harness/research/tests/test_synthesis.py` | SynthesisAgent tests (mock anthropic) |
| `backend/app/harness/research/tests/test_tool.py` | ResearchTool integration tests |
| `backend/app/harness/skill_tools.py` | Add `register_research_tools()` call |
| `backend/app/harness/loop.py` | Add `"research"` to `PARALLEL_SAFE_TOOLS` |

---

## Task 1: Package skeleton + types

**Files:**
- Create: `backend/app/harness/research/__init__.py`
- Create: `backend/app/harness/research/modules/__init__.py`
- Create: `backend/app/harness/research/tests/__init__.py`
- Create: `backend/app/harness/research/types.py`
- Create: `backend/app/harness/research/tests/test_types.py`

- [ ] **Step 1: Create directories**

```bash
mkdir -p backend/app/harness/research/modules
mkdir -p backend/app/harness/research/tests
touch backend/app/harness/research/__init__.py
touch backend/app/harness/research/modules/__init__.py
touch backend/app/harness/research/tests/__init__.py
```

- [ ] **Step 2: Write failing tests for types**

Create `backend/app/harness/research/tests/test_types.py`:

```python
from __future__ import annotations

from app.harness.research.types import (
    CodeExample,
    CodeResult,
    PaperFinding,
    PapersResult,
    ResearchResult,
    RoutePlan,
    WebPage,
    WebResult,
)


def test_paper_finding_defaults():
    pf = PaperFinding(title="Test", key_finding="finding", source="arxiv")
    assert pf.arxiv_id is None
    assert pf.year is None
    assert pf.citation_count is None
    assert pf.section_excerpts == []


def test_research_result_budget_warning_default():
    rr = ResearchResult(
        summary="test",
        papers=[],
        code_examples=[],
        web_refs=[],
        follow_up_questions=[],
        modules_ran=["papers"],
        total_ms=100,
        budget_tokens_used=150_000,
    )
    assert rr.budget_warning is None


def test_route_plan_structure():
    plan = RoutePlan(
        modules=["papers", "code"],
        sub_queries={"papers": "q1", "code": "q2"},
        budgets={"papers": 90_000, "code": 60_000},
        parallel_ok=True,
        rationale="independent queries",
    )
    assert plan.budgets["papers"] == 90_000
    assert plan.parallel_ok is True


def test_budget_warning_set():
    rr = ResearchResult(
        summary="test",
        papers=[],
        code_examples=[],
        web_refs=[],
        follow_up_questions=[],
        modules_ran=["papers"],
        total_ms=100,
        budget_tokens_used=1_000_000,
        budget_warning="Hard cap applied.",
    )
    assert rr.budget_warning is not None
```

- [ ] **Step 3: Run tests — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_types.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.harness.research'`

- [ ] **Step 4: Write types.py**

Create `backend/app/harness/research/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PaperFinding:
    title: str
    key_finding: str          # one sentence: result + recipe
    source: str               # "hf_papers" | "semantic_scholar" | "arxiv"
    arxiv_id: str | None = None
    year: int | None = None
    citation_count: int | None = None
    section_excerpts: list[str] = field(default_factory=list)


@dataclass
class PapersResult:
    papers: list[PaperFinding] = field(default_factory=list)
    crawl_depth: int = 0


@dataclass
class CodeExample:
    url: str
    repo: str
    file_path: str
    snippet: str              # ≤500 chars
    relevance: str            # one sentence
    stars: int | None = None


@dataclass
class CodeResult:
    examples: list[CodeExample] = field(default_factory=list)


@dataclass
class WebPage:
    url: str
    title: str
    summary: str              # ≤300 chars


@dataclass
class WebResult:
    pages: list[WebPage] = field(default_factory=list)


@dataclass
class RoutePlan:
    modules: list[str]
    sub_queries: dict[str, str]
    budgets: dict[str, int]
    parallel_ok: bool
    rationale: str


@dataclass
class ResearchResult:
    summary: str
    papers: list[PaperFinding]
    code_examples: list[CodeExample]
    web_refs: list[WebPage]
    follow_up_questions: list[str]
    modules_ran: list[str]
    total_ms: int
    budget_tokens_used: int
    budget_warning: str | None = None
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_types.py -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/harness/research/
git commit -m "feat(research): package skeleton + types"
```

---

## Task 2: JobRegistry

**Files:**
- Create: `backend/app/harness/research/jobs.py`
- Create: `backend/app/harness/research/tests/test_jobs.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_jobs.py`:

```python
from __future__ import annotations

import time

from app.harness.research.jobs import JobRegistry
from app.harness.research.types import ResearchResult


def _make_result() -> ResearchResult:
    return ResearchResult(
        summary="done", papers=[], code_examples=[], web_refs=[],
        follow_up_questions=[], modules_ran=["papers"],
        total_ms=50, budget_tokens_used=150_000,
    )


def test_create_and_get_running():
    reg = JobRegistry()
    job_id = reg.create(query="test", sources=["papers"], estimated_seconds=30)
    snap = reg.get(job_id)
    assert snap["status"] == "running"
    assert snap["elapsed_seconds"] >= 0
    assert snap["estimated_seconds"] == 30
    assert snap["progress"] == {}
    assert snap["partial_result"] == {}


def test_complete_job():
    reg = JobRegistry()
    job_id = reg.create(query="test", sources=["papers"], estimated_seconds=10)
    reg.complete(job_id, _make_result())
    snap = reg.get(job_id)
    assert snap["status"] == "done"
    assert snap["result"]["summary"] == "done"


def test_fail_job():
    reg = JobRegistry()
    job_id = reg.create(query="fail", sources=["code"], estimated_seconds=5)
    reg.fail(job_id, "network error")
    snap = reg.get(job_id)
    assert snap["status"] == "failed"
    assert snap["error"] == "network error"


def test_update_partial():
    reg = JobRegistry()
    job_id = reg.create(query="test", sources=["papers", "code"], estimated_seconds=20)
    reg.update_partial(job_id, "papers", [{"title": "P1"}])
    snap = reg.get(job_id)
    assert snap["progress"]["papers"] == "done"
    assert snap["partial_result"]["papers"] == [{"title": "P1"}]
    assert snap["progress"].get("code") is None


def test_not_found():
    reg = JobRegistry()
    snap = reg.get("nonexistent-id")
    assert snap["status"] == "not_found"


def test_ttl_expiry():
    reg = JobRegistry(ttl_seconds=0)
    job_id = reg.create(query="old", sources=["web"], estimated_seconds=5)
    reg.complete(job_id, _make_result())
    time.sleep(0.01)
    snap = reg.get(job_id)
    assert snap["status"] == "not_found"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_jobs.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.harness.research.jobs'`

- [ ] **Step 3: Write jobs.py**

Create `backend/app/harness/research/jobs.py`:

```python
from __future__ import annotations

import dataclasses
import time
import uuid
from threading import RLock
from typing import Any

from app.harness.research.types import ResearchResult

_DEFAULT_TTL = 1800  # 30 minutes


def _result_to_dict(r: ResearchResult) -> dict[str, Any]:
    return dataclasses.asdict(r)


class JobRegistry:
    """Thread-safe in-memory store for async research jobs."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL) -> None:
        self._ttl = ttl_seconds
        self._lock = RLock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def create(self, query: str, sources: list[str], estimated_seconds: int) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "started_at": time.monotonic(),
                "query": query,
                "sources": sources,
                "estimated_seconds": estimated_seconds,
                "result": None,
                "error": None,
                "partial": {},   # module_name -> serialized findings
                "progress": {},  # module_name -> "done"
            }
        return job_id

    def complete(self, job_id: str, result: ResearchResult) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "done"
                self._jobs[job_id]["result"] = _result_to_dict(result)
                self._jobs[job_id]["completed_at"] = time.monotonic()

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = error
                self._jobs[job_id]["completed_at"] = time.monotonic()

    def update_partial(self, job_id: str, module: str, findings: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["partial"][module] = findings
                self._jobs[job_id]["progress"][module] = "done"

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"status": "not_found"}
            # TTL check: only expire completed/failed jobs
            if job["status"] in ("done", "failed"):
                completed_at = job.get("completed_at", job["started_at"])
                if time.monotonic() - completed_at > self._ttl:
                    del self._jobs[job_id]
                    return {"status": "not_found"}
            elapsed = int(time.monotonic() - job["started_at"])
            return {
                "status": job["status"],
                "elapsed_seconds": elapsed,
                "estimated_seconds": job["estimated_seconds"],
                "progress": dict(job["progress"]),
                "partial_result": dict(job["partial"]),
                "result": job.get("result"),
                "error": job.get("error"),
            }
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_jobs.py -v 2>&1 | tail -15
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/jobs.py backend/app/harness/research/tests/test_jobs.py
git commit -m "feat(research): JobRegistry with TTL expiry"
```

---

## Task 3: PapersModule

**Files:**
- Create: `backend/app/harness/research/modules/papers.py`
- Create: `backend/app/harness/research/tests/test_papers.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_papers.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.harness.research.modules.papers import PapersModule, _estimate_tokens, _recency_query


def test_estimate_tokens():
    assert _estimate_tokens("hello world") == 3   # 11 chars // 4


def test_recency_query_detected():
    assert _recency_query("recent calibration methods 2025") is True
    assert _recency_query("state of the art transformer") is True
    assert _recency_query("Platt 1999 calibration") is False


def test_run_returns_empty_on_all_failures():
    module = PapersModule()
    with patch.object(module, "_search_hf_papers", return_value=[]):
        with patch.object(module, "_search_semantic_scholar", return_value=[]):
            result = module.run("calibration", budget_tokens=10_000)
    assert result.papers == []
    assert result.crawl_depth == 0


def test_run_uses_hf_papers_for_recent_query():
    module = PapersModule()
    mock_paper = MagicMock()
    mock_paper.title = "Recent Calibration"
    mock_paper.arxiv_id = "2501.99999"
    mock_paper.year = 2025
    mock_paper.citation_count = 5
    mock_paper.source = "hf_papers"

    with patch.object(module, "_search_hf_papers", return_value=[mock_paper]) as mock_hf:
        with patch.object(module, "_search_semantic_scholar", return_value=[]):
            result = module.run("recent calibration 2025", budget_tokens=50_000)
    mock_hf.assert_called_once()
    assert len(result.papers) >= 1


def test_run_respects_budget():
    module = PapersModule()
    calls = []

    def fake_hf(query: str) -> list:
        calls.append("hf")
        return []

    def fake_s2(query: str) -> list:
        calls.append("s2")
        return []

    with patch.object(module, "_search_hf_papers", side_effect=fake_hf):
        with patch.object(module, "_search_semantic_scholar", side_effect=fake_s2):
            # budget of 1 token → module should not make expensive calls
            result = module.run("test", budget_tokens=1)
    assert result.papers == []


def test_s2_rate_limit_falls_back_to_arxiv():
    module = PapersModule()
    with patch.object(module, "_search_semantic_scholar", side_effect=Exception("429")):
        with patch.object(module, "_search_arxiv", return_value=[]) as mock_arxiv:
            result = module.run("calibration sigmoid", budget_tokens=50_000)
    mock_arxiv.assert_called_once()
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_papers.py -v 2>&1 | tail -10
```

- [ ] **Step 3: Write papers.py**

Create `backend/app/harness/research/modules/papers.py`:

```python
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import httpx

from app.harness.research.types import PaperFinding, PapersResult

logger = logging.getLogger(__name__)

_HF_API = "https://huggingface.co/api/papers"
_S2_API = "https://api.semanticscholar.org/graph/v1"
_ARXIV_API = "https://export.arxiv.org/api/query"
_ARXIV_HTML = "https://ar5iv.labs.arxiv.org/html"

_RECENCY_SIGNALS = {"recent", "new", "latest", "2024", "2025", "2026", "state of the art", "sota"}
_S2_TIMEOUT = 12
_S2_RATE_LIMIT_WAIT = 10  # seconds


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _recency_query(query: str) -> bool:
    lower = query.lower()
    return any(sig in lower for sig in _RECENCY_SIGNALS)


@dataclass
class _RawPaper:
    title: str
    arxiv_id: str | None
    year: int | None
    citation_count: int | None
    abstract: str
    source: str


class PapersModule:
    """Searches HF Papers, Semantic Scholar, and ArXiv for relevant papers."""

    def __init__(self) -> None:
        self._s2_headers: dict[str, str] = {}
        api_key = os.environ.get("S2_API_KEY")
        if api_key:
            self._s2_headers["x-api-key"] = api_key

    def run(self, query: str, budget_tokens: int) -> PapersResult:
        if budget_tokens < 1_000:
            return PapersResult()

        papers: list[PaperFinding] = []
        tokens_used = 0
        crawl_depth = 0

        # Strategy: recency queries start at HF Papers; others start at S2
        if _recency_query(query):
            hf_results = self._search_hf_papers(query)
            for raw in hf_results[:5]:
                tokens_used += _estimate_tokens(raw.abstract)
                if tokens_used > budget_tokens * 0.9:
                    break
                papers.append(self._raw_to_finding(raw))
            if not papers:
                papers.extend(self._s2_search_safe(query, budget_tokens, tokens_used))
        else:
            papers.extend(self._s2_search_safe(query, budget_tokens, tokens_used))

        # Citation graph: take top anchor paper and crawl one level if budget remains
        if papers and tokens_used < budget_tokens * 0.7:
            anchor_id = papers[0].arxiv_id
            if anchor_id:
                downstream = self._citation_graph(anchor_id, budget_tokens - tokens_used)
                papers.extend(downstream)
                crawl_depth = 1

        return PapersResult(papers=papers[:20], crawl_depth=crawl_depth)

    # ── Source: HF Papers ─────────────────────────────────────────────────────

    def _search_hf_papers(self, query: str) -> list[_RawPaper]:
        try:
            resp = httpx.get(_HF_API, params={"q": query}, timeout=10)
            resp.raise_for_status()
            items = resp.json() if isinstance(resp.json(), list) else resp.json().get("papers", [])
            results = []
            for item in items[:10]:
                results.append(_RawPaper(
                    title=item.get("title", ""),
                    arxiv_id=item.get("id") or item.get("arxivId"),
                    year=item.get("publishedAt", "")[:4] or None,
                    citation_count=item.get("upvotes"),
                    abstract=item.get("summary", item.get("abstract", ""))[:800],
                    source="hf_papers",
                ))
            return results
        except Exception as exc:
            logger.debug("HF Papers fetch failed: %s", exc)
            return []

    # ── Source: Semantic Scholar ──────────────────────────────────────────────

    def _search_semantic_scholar(self, query: str) -> list[_RawPaper]:
        params = {
            "query": query,
            "fields": "title,year,citationCount,abstract,externalIds",
            "limit": 10,
        }
        resp = httpx.get(
            f"{_S2_API}/paper/search",
            params=params,
            headers=self._s2_headers,
            timeout=_S2_TIMEOUT,
        )
        if resp.status_code == 429:
            raise Exception("429")
        resp.raise_for_status()
        data = resp.json().get("data", [])
        results = []
        for item in data:
            ext = item.get("externalIds") or {}
            results.append(_RawPaper(
                title=item.get("title", ""),
                arxiv_id=ext.get("ArXiv"),
                year=item.get("year"),
                citation_count=item.get("citationCount"),
                abstract=item.get("abstract", "")[:800],
                source="semantic_scholar",
            ))
        return results

    def _s2_search_safe(
        self, query: str, budget_tokens: int, tokens_used: int
    ) -> list[PaperFinding]:
        try:
            raws = self._search_semantic_scholar(query)
        except Exception as exc:
            if "429" in str(exc):
                logger.warning("S2 rate-limited — falling back to ArXiv")
                raws = self._search_arxiv(query)
            else:
                logger.debug("S2 search failed: %s", exc)
                raws = self._search_arxiv(query)
        findings = []
        for raw in raws[:8]:
            tokens_used += _estimate_tokens(raw.abstract)
            if tokens_used > budget_tokens * 0.9:
                break
            findings.append(self._raw_to_finding(raw))
        return findings

    def _citation_graph(self, arxiv_id: str, remaining_budget: int) -> list[PaperFinding]:
        if remaining_budget < 5_000:
            return []
        try:
            resp = httpx.get(
                f"{_S2_API}/paper/ARXIV:{arxiv_id}/citations",
                params={"fields": "title,year,citationCount,abstract,externalIds", "limit": 10},
                headers=self._s2_headers,
                timeout=_S2_TIMEOUT,
            )
            if resp.status_code == 429:
                return []
            resp.raise_for_status()
            items = resp.json().get("data", [])
            results = []
            tokens_used = 0
            for item in items:
                citing = item.get("citingPaper", {})
                ext = citing.get("externalIds") or {}
                abstract = citing.get("abstract", "")[:800]
                tokens_used += _estimate_tokens(abstract)
                if tokens_used > remaining_budget * 0.9:
                    break
                results.append(PaperFinding(
                    title=citing.get("title", ""),
                    arxiv_id=ext.get("ArXiv"),
                    year=citing.get("year"),
                    citation_count=citing.get("citationCount"),
                    key_finding="downstream citation — see abstract",
                    section_excerpts=[abstract] if abstract else [],
                    source="semantic_scholar",
                ))
            return results
        except Exception as exc:
            logger.debug("Citation graph failed: %s", exc)
            return []

    # ── Source: ArXiv ─────────────────────────────────────────────────────────

    def _search_arxiv(self, query: str) -> list[_RawPaper]:
        try:
            resp = httpx.get(
                _ARXIV_API,
                params={"search_query": f"all:{query}", "max_results": 8, "sortBy": "relevance"},
                timeout=10,
            )
            resp.raise_for_status()
            # Parse Atom XML minimally
            text = resp.text
            results = []
            import re
            entries = re.findall(r"<entry>(.*?)</entry>", text, re.DOTALL)
            for entry in entries[:8]:
                title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                id_m = re.search(r"<id>.*?/abs/([\w.]+)</id>", entry)
                summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                year_m = re.search(r"<published>(\d{4})", entry)
                results.append(_RawPaper(
                    title=(title_m.group(1).strip() if title_m else ""),
                    arxiv_id=(id_m.group(1) if id_m else None),
                    year=(int(year_m.group(1)) if year_m else None),
                    citation_count=None,
                    abstract=(summary_m.group(1).strip()[:800] if summary_m else ""),
                    source="arxiv",
                ))
            return results
        except Exception as exc:
            logger.debug("ArXiv search failed: %s", exc)
            return []

    def _raw_to_finding(self, raw: _RawPaper) -> PaperFinding:
        return PaperFinding(
            title=raw.title,
            arxiv_id=raw.arxiv_id,
            year=int(raw.year) if raw.year else None,
            citation_count=raw.citation_count,
            key_finding=raw.abstract[:200] if raw.abstract else "see paper",
            section_excerpts=[raw.abstract] if raw.abstract else [],
            source=raw.source,
        )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_papers.py -v 2>&1 | tail -15
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/modules/papers.py backend/app/harness/research/tests/test_papers.py
git commit -m "feat(research): PapersModule — HF Papers + S2 + ArXiv"
```

---

## Task 4: CodeModule

**Files:**
- Create: `backend/app/harness/research/modules/code.py`
- Create: `backend/app/harness/research/tests/test_code.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_code.py`:

```python
from __future__ import annotations

from unittest.mock import patch

from app.harness.research.modules.code import CodeModule


def test_run_returns_empty_when_gh_unavailable():
    module = CodeModule()
    with patch.object(module, "_gh_search", return_value=[]):
        result = module.run("isotonic calibration", budget_tokens=30_000)
    assert result.examples == []


def test_run_respects_budget():
    module = CodeModule()
    result = module.run("test", budget_tokens=100)
    assert result.examples == []


def test_gh_search_parses_output():
    module = CodeModule()
    fake_output = (
        'url\trepo\tfile_path\n'
        'https://github.com/org/repo/blob/main/train.py\torg/repo\ttrain.py\n'
    )
    with patch.object(module, "_run_gh", return_value=fake_output):
        items = module._gh_search("calibration sklearn")
    assert len(items) == 1
    assert items[0]["repo"] == "org/repo"


def test_run_deduplicates_repos():
    module = CodeModule()
    same_repo_items = [
        {"url": f"https://github.com/org/repo/blob/main/file{i}.py",
         "repo": "org/repo", "file_path": f"file{i}.py"}
        for i in range(10)
    ]
    with patch.object(module, "_gh_search", return_value=same_repo_items):
        with patch.object(module, "_read_file_snippet", return_value="code snippet"):
            result = module.run("test", budget_tokens=30_000)
    # Should not return 10 examples from same repo
    repos = {ex.repo for ex in result.examples}
    assert len(repos) <= 5
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_code.py -v 2>&1 | tail -8
```

- [ ] **Step 3: Write code.py**

Create `backend/app/harness/research/modules/code.py`:

```python
from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any

from app.harness.research.types import CodeExample, CodeResult

logger = logging.getLogger(__name__)

_GH_TIMEOUT = 15
_MAX_SNIPPET_CHARS = 500
_MAX_REPOS = 5


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


class CodeModule:
    """Searches GitHub for working code examples using the gh CLI."""

    def run(self, query: str, budget_tokens: int) -> CodeResult:
        if budget_tokens < 1_000 or not shutil.which("gh"):
            return CodeResult()

        items = self._gh_search(query)
        if not items:
            return CodeResult()

        examples: list[CodeExample] = []
        tokens_used = 0
        seen_repos: set[str] = set()

        for item in items:
            repo = item.get("repo", "")
            if repo in seen_repos and len(seen_repos) >= _MAX_REPOS:
                continue
            seen_repos.add(repo)

            snippet = self._read_file_snippet(item.get("url", ""))
            tokens_used += _estimate_tokens(snippet)
            if tokens_used > budget_tokens * 0.9:
                break

            examples.append(CodeExample(
                url=item.get("url", ""),
                repo=repo,
                file_path=item.get("file_path", ""),
                snippet=snippet[:_MAX_SNIPPET_CHARS],
                relevance=f"Matches query: {query[:80]}",
                stars=item.get("stars"),
            ))

        return CodeResult(examples=examples)

    def _run_gh(self, args: list[str]) -> str:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True, text=True, timeout=_GH_TIMEOUT,
        )
        return result.stdout if result.returncode == 0 else ""

    def _gh_search(self, query: str) -> list[dict[str, Any]]:
        output = self._run_gh([
            "search", "code", query,
            "--language", "python",
            "--limit", "20",
            "--json", "url,repository,path",
        ])
        if not output:
            # Fallback: plain text search
            output = self._run_gh(["search", "code", query, "--limit", "10"])
            return self._parse_plain(output)
        try:
            import json
            items = json.loads(output)
            return [
                {
                    "url": item.get("url", ""),
                    "repo": item.get("repository", {}).get("fullName", ""),
                    "file_path": item.get("path", ""),
                    "stars": item.get("repository", {}).get("stargazersCount"),
                }
                for item in items
            ]
        except Exception:
            return self._parse_plain(output)

    def _parse_plain(self, output: str) -> list[dict[str, Any]]:
        items = []
        for line in output.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                items.append({"url": parts[0], "repo": parts[1], "file_path": parts[2]})
        return items

    def _read_file_snippet(self, url: str) -> str:
        if not url or "github.com" not in url:
            return ""
        try:
            # Convert blob URL to API path
            # https://github.com/org/repo/blob/main/path → org/repo + path
            parts = url.replace("https://github.com/", "").split("/blob/", 1)
            if len(parts) != 2:
                return ""
            repo = parts[0]
            ref_path = parts[1].split("/", 1)
            if len(ref_path) != 2:
                return ""
            file_path = ref_path[1]
            output = self._run_gh([
                "api", f"repos/{repo}/contents/{file_path}",
                "--jq", ".content",
            ])
            if output:
                import base64
                content = base64.b64decode(output.strip()).decode("utf-8", errors="ignore")
                return content[:_MAX_SNIPPET_CHARS]
        except Exception as exc:
            logger.debug("File read failed for %s: %s", url, exc)
        return ""
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_code.py -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/modules/code.py backend/app/harness/research/tests/test_code.py
git commit -m "feat(research): CodeModule — gh CLI code search"
```

---

## Task 5: WebModule

**Files:**
- Create: `backend/app/harness/research/modules/web.py`
- Create: `backend/app/harness/research/tests/test_web.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_web.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.harness.research.modules.web import WebModule, _strip_html, _extract_title


def test_strip_html_removes_tags():
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    assert "Hello world" in _strip_html(html)
    assert "<" not in _strip_html(html)


def test_extract_title():
    html = "<html><head><title>My Page</title></head><body></body></html>"
    assert _extract_title(html) == "My Page"


def test_extract_title_missing():
    assert _extract_title("<html><body>no title</body></html>") == ""


def test_run_skips_on_tiny_budget():
    module = WebModule()
    result = module.run(["https://example.com"], budget_tokens=10)
    assert result.pages == []


def test_run_fetches_and_strips():
    module = WebModule()
    fake_html = "<html><head><title>Test Page</title></head><body><p>Important content here.</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp):
        result = module.run(["https://example.com/test"], budget_tokens=20_000)

    assert len(result.pages) == 1
    assert result.pages[0].title == "Test Page"
    assert "Important content" in result.pages[0].summary


def test_run_skips_failed_fetch():
    module = WebModule()
    with patch("httpx.get", side_effect=Exception("timeout")):
        result = module.run(["https://example.com"], budget_tokens=20_000)
    assert result.pages == []
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_web.py -v 2>&1 | tail -8
```

- [ ] **Step 3: Write web.py**

Create `backend/app/harness/research/modules/web.py`:

```python
from __future__ import annotations

import logging
import re

import httpx

from app.harness.research.types import WebPage, WebResult

logger = logging.getLogger(__name__)

_MAX_SUMMARY = 300
_FETCH_TIMEOUT = 10


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


class WebModule:
    """Fetches and summarises targeted web pages."""

    def run(self, urls: list[str], budget_tokens: int) -> WebResult:
        if budget_tokens < 1_000:
            return WebResult()

        pages: list[WebPage] = []
        tokens_used = 0

        for url in urls[:5]:
            try:
                resp = httpx.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
                resp.raise_for_status()
                html = resp.text
            except Exception as exc:
                logger.debug("Web fetch failed for %s: %s", url, exc)
                continue

            title = _extract_title(html)
            text = _strip_html(html)
            tokens_used += len(text) // 4

            if tokens_used > budget_tokens * 0.9:
                break

            summary = text[:_MAX_SUMMARY]
            pages.append(WebPage(url=url, title=title, summary=summary))

        return WebResult(pages=pages)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_web.py -v 2>&1 | tail -10
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/modules/web.py backend/app/harness/research/tests/test_web.py
git commit -m "feat(research): WebModule — targeted httpx fetch"
```

---

## Task 6: RoutingAgent

**Files:**
- Create: `backend/app/harness/research/router.py`
- Create: `backend/app/harness/research/tests/test_router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_router.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.harness.research.router import RoutingAgent
from app.harness.research.types import RoutePlan


def _mock_anthropic(json_content: dict) -> MagicMock:
    mock_api = MagicMock()
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = json.dumps(json_content)
    mock_msg.content = [mock_block]
    mock_api.messages.create.return_value = mock_msg
    return mock_api


def test_route_parallel_query():
    plan_json = {
        "modules": ["papers", "code"],
        "sub_queries": {"papers": "calibration methods", "code": "calibration sklearn"},
        "budgets": {"papers": 90_000, "code": 60_000},
        "parallel_ok": True,
        "rationale": "independent queries",
    }
    router = RoutingAgent(api_client=_mock_anthropic(plan_json))
    plan = router.route(
        query="isotonic calibration LightGBM",
        context="",
        sources=["papers", "code", "web"],
        budget_tokens=150_000,
    )
    assert isinstance(plan, RoutePlan)
    assert plan.parallel_ok is True
    assert "papers" in plan.modules
    assert plan.budgets["papers"] == 90_000


def test_route_falls_back_on_invalid_json():
    mock_api = MagicMock()
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "not valid json at all"
    mock_msg.content = [mock_block]
    mock_api.messages.create.return_value = mock_msg

    router = RoutingAgent(api_client=mock_api)
    plan = router.route(
        query="test", context="", sources=["papers", "code"], budget_tokens=100_000,
    )
    # Fallback: run all requested modules with equal budget
    assert set(plan.modules) == {"papers", "code"}
    assert plan.parallel_ok is True


def test_route_falls_back_on_api_error():
    mock_api = MagicMock()
    mock_api.messages.create.side_effect = Exception("API error")

    router = RoutingAgent(api_client=mock_api)
    plan = router.route(
        query="test", context="", sources=["papers"], budget_tokens=50_000,
    )
    assert plan.modules == ["papers"]
    assert plan.budgets["papers"] == 50_000


def test_budget_not_allocated_to_unselected_modules():
    plan_json = {
        "modules": ["papers"],
        "sub_queries": {"papers": "distribution shift finance"},
        "budgets": {"papers": 150_000},
        "parallel_ok": True,
        "rationale": "papers only",
    }
    router = RoutingAgent(api_client=_mock_anthropic(plan_json))
    plan = router.route("finance", "", ["papers", "code", "web"], 150_000)
    assert "code" not in plan.modules
    assert "web" not in plan.modules
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_router.py -v 2>&1 | tail -8
```

- [ ] **Step 3: Write router.py**

Create `backend/app/harness/research/router.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from app.harness.research.types import RoutePlan

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 512

_SYSTEM_PROMPT = """\
You are the routing agent for a research tool used by data scientists, ML engineers,
and quantitative analysts. Your job: given a research query, decide which source
modules to run, craft the best sub-query for each, allocate the token budget, and
determine if modules can run in parallel.

# Your default approach: start from the literature

Do not default to code or web first. Papers contain results — results tell you what
actually works. Only skip papers if the query is explicitly about implementation
details or a specific codebase.

## When to run modules in parallel

Run in parallel when each module can answer its sub-query independently:
- "best isotonic calibration methods" → papers + code simultaneously (parallel_ok: true)
- "find the dataset used in the Guo 2017 calibration paper" → papers first, then
  code/web with the dataset name (parallel_ok: false)

Rule: parallel_ok is false only when one module's output is the *input* to another's query.

## Budget allocation principles

You receive a total budget and must split it across the modules you select.
Allocation guidance:
- Papers crawls are expensive (citation graphs, section reads): give papers 50-70% when included
- Code search is cheap: 20-30% is usually enough
- Web fetch is cheapest: 10-20%
- If only one module runs, give it the full budget
- Never allocate less than 10,000 tokens to any module you include

## Output format

Respond ONLY with valid JSON. No prose before or after.

{
  "modules": ["papers", "code"],
  "sub_queries": {
    "papers": "isotonic regression calibration post-hoc methods imbalanced classification",
    "code": "isotonic calibration sklearn LightGBM example"
  },
  "budgets": {
    "papers": 90000,
    "code": 60000
  },
  "parallel_ok": true,
  "rationale": "one sentence explaining the routing decision"
}"""

_USER_TEMPLATE = """\
Query: {query}
Context: {context}
Available sources: {sources}
Total budget (tokens): {budget_tokens}

Route this query."""


def _fallback_plan(sources: list[str], budget_tokens: int, query: str) -> RoutePlan:
    """Run all requested sources with equal budget split."""
    per_module = max(10_000, budget_tokens // max(len(sources), 1))
    return RoutePlan(
        modules=list(sources),
        sub_queries={s: query for s in sources},
        budgets={s: per_module for s in sources},
        parallel_ok=True,
        rationale="fallback: equal split across all sources",
    )


class RoutingAgent:
    def __init__(self, api_client: Any) -> None:
        self._api = api_client

    def route(
        self,
        query: str,
        context: str,
        sources: list[str],
        budget_tokens: int,
    ) -> RoutePlan:
        user_msg = _USER_TEMPLATE.format(
            query=query,
            context=context or "none",
            sources=", ".join(sources),
            budget_tokens=budget_tokens,
        )
        try:
            resp = self._api.messages.create(
                model=_MODEL,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=_MAX_TOKENS,
            )
            text = ""
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    text += block.text
            data = json.loads(text.strip())
            return RoutePlan(
                modules=data["modules"],
                sub_queries=data["sub_queries"],
                budgets=data["budgets"],
                parallel_ok=bool(data.get("parallel_ok", True)),
                rationale=data.get("rationale", ""),
            )
        except Exception as exc:
            logger.warning("RoutingAgent failed (%s) — using fallback plan", exc)
            return _fallback_plan(sources, budget_tokens, query)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_router.py -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/router.py backend/app/harness/research/tests/test_router.py
git commit -m "feat(research): RoutingAgent — haiku LLM routing with ml-intern-style prompt"
```

---

## Task 7: SynthesisAgent

**Files:**
- Create: `backend/app/harness/research/synthesis.py`
- Create: `backend/app/harness/research/tests/test_synthesis.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_synthesis.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.harness.research.synthesis import SynthesisAgent
from app.harness.research.types import (
    CodeExample,
    CodeResult,
    PaperFinding,
    PapersResult,
    WebResult,
)


def _mock_api(summary_text: str) -> MagicMock:
    mock_api = MagicMock()
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = json.dumps({
        "summary": summary_text,
        "follow_up_questions": ["What dataset should I use?"],
    })
    mock_msg.content = [mock_block]
    mock_api.messages.create.return_value = mock_msg
    return mock_api


def test_synthesise_basic():
    papers = PapersResult(papers=[
        PaperFinding(title="Guo 2017", key_finding="temperature scaling works",
                     source="semantic_scholar", arxiv_id="1706.04599"),
    ], crawl_depth=1)
    code = CodeResult(examples=[
        CodeExample(url="https://github.com/org/repo/blob/main/cal.py",
                    repo="org/repo", file_path="cal.py",
                    snippet="from sklearn.calibration import CalibratedClassifierCV",
                    relevance="sklearn calibration example"),
    ])
    web = WebResult()

    agent = SynthesisAgent(api_client=_mock_api("Temperature scaling is the best approach."))
    result = agent.synthesise(
        query="calibration methods",
        context="",
        papers=papers,
        code=code,
        web=web,
        modules_ran=["papers", "code"],
        total_ms=1200,
        budget_tokens_used=150_000,
    )
    assert result.summary == "Temperature scaling is the best approach."
    assert len(result.papers) == 1
    assert len(result.code_examples) == 1
    assert result.modules_ran == ["papers", "code"]
    assert result.total_ms == 1200
    assert result.budget_warning is None


def test_synthesise_sets_budget_warning():
    agent = SynthesisAgent(api_client=_mock_api("summary"))
    result = agent.synthesise(
        query="q", context="", papers=PapersResult(), code=CodeResult(), web=WebResult(),
        modules_ran=[], total_ms=0, budget_tokens_used=1_000_000,
        budget_warning="Hard cap applied.",
    )
    assert result.budget_warning == "Hard cap applied."


def test_synthesise_falls_back_on_api_error():
    mock_api = MagicMock()
    mock_api.messages.create.side_effect = Exception("API down")
    agent = SynthesisAgent(api_client=mock_api)
    result = agent.synthesise(
        query="test", context="", papers=PapersResult(), code=CodeResult(), web=WebResult(),
        modules_ran=["papers"], total_ms=500, budget_tokens_used=50_000,
    )
    # Fallback: returns a basic result with no summary
    assert result.modules_ran == ["papers"]
    assert isinstance(result.summary, str)
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_synthesis.py -v 2>&1 | tail -8
```

- [ ] **Step 3: Write synthesis.py**

Create `backend/app/harness/research/synthesis.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from app.harness.research.types import (
    CodeResult,
    PapersResult,
    ResearchResult,
    WebResult,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024

_SYSTEM_PROMPT = """\
You are a synthesis agent. You receive research findings from multiple source modules
(papers, code examples, web pages) and produce a structured summary for a data scientist
or ML engineer.

Your output MUST be valid JSON with this exact shape:
{
  "summary": "2-4 sentences directly answering the query, citing specific findings",
  "follow_up_questions": ["question if more research needed", ...]
}

Rules:
- summary must cite specific papers, methods, or code found — not generic statements
- follow_up_questions: 0-3 questions the agent should research next; empty list if none needed
- Respond ONLY with the JSON object. No prose before or after."""


class SynthesisAgent:
    def __init__(self, api_client: Any) -> None:
        self._api = api_client

    def synthesise(
        self,
        query: str,
        context: str,
        papers: PapersResult,
        code: CodeResult,
        web: WebResult,
        modules_ran: list[str],
        total_ms: int,
        budget_tokens_used: int,
        budget_warning: str | None = None,
    ) -> ResearchResult:
        user_msg = self._build_user_message(query, context, papers, code, web)
        summary = ""
        follow_ups: list[str] = []

        try:
            resp = self._api.messages.create(
                model=_MODEL,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=_MAX_TOKENS,
            )
            text = ""
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    text += block.text
            data = json.loads(text.strip())
            summary = data.get("summary", "")
            follow_ups = data.get("follow_up_questions", [])
        except Exception as exc:
            logger.warning("SynthesisAgent failed (%s) — using raw results", exc)
            summary = f"Research completed across {modules_ran}. See papers and code below."

        return ResearchResult(
            summary=summary,
            papers=papers.papers,
            code_examples=code.examples,
            web_refs=web.pages,
            follow_up_questions=follow_ups,
            modules_ran=modules_ran,
            total_ms=total_ms,
            budget_tokens_used=budget_tokens_used,
            budget_warning=budget_warning,
        )

    def _build_user_message(
        self,
        query: str,
        context: str,
        papers: PapersResult,
        code: CodeResult,
        web: WebResult,
    ) -> str:
        parts = [f"Query: {query}"]
        if context:
            parts.append(f"Context: {context}")

        if papers.papers:
            parts.append(f"\n## Papers found ({len(papers.papers)})")
            for p in papers.papers[:10]:
                parts.append(f"- [{p.source}] {p.title} ({p.year}): {p.key_finding}")

        if code.examples:
            parts.append(f"\n## Code examples found ({len(code.examples)})")
            for ex in code.examples[:5]:
                parts.append(f"- {ex.repo}: {ex.relevance}\n  {ex.snippet[:200]}")

        if web.pages:
            parts.append(f"\n## Web pages found ({len(web.pages)})")
            for pg in web.pages[:3]:
                parts.append(f"- {pg.title}: {pg.summary}")

        parts.append("\nSynthesize these findings.")
        return "\n".join(parts)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_synthesis.py -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/synthesis.py backend/app/harness/research/tests/test_synthesis.py
git commit -m "feat(research): SynthesisAgent — haiku LLM merge pass"
```

---

## Task 8: ResearchTool orchestrator

**Files:**
- Create: `backend/app/harness/research/tool.py`
- Create: `backend/app/harness/research/tests/test_tool.py`

- [ ] **Step 1: Write failing tests**

Create `backend/app/harness/research/tests/test_tool.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.harness.research.tool import RESEARCH_SCHEMAS, ResearchTool
from app.harness.research.types import (
    CodeResult,
    PapersResult,
    ResearchResult,
    WebResult,
)


def _make_result(summary: str = "done") -> ResearchResult:
    return ResearchResult(
        summary=summary, papers=[], code_examples=[], web_refs=[],
        follow_up_questions=[], modules_ran=["papers"],
        total_ms=100, budget_tokens_used=150_000,
    )


def test_schemas_define_three_tools():
    names = [s.name for s in RESEARCH_SCHEMAS]
    assert "research" in names
    assert "research_start" in names
    assert "research_get" in names


def test_execute_clamps_budget_over_1m():
    tool = ResearchTool.__new__(ResearchTool)
    tool._jobs = MagicMock()
    tool._routing_agent = MagicMock()
    tool._synthesis_agent = MagicMock()

    from app.harness.research.types import RoutePlan
    tool._routing_agent.route.return_value = RoutePlan(
        modules=["papers"],
        sub_queries={"papers": "test"},
        budgets={"papers": 1_000_000},
        parallel_ok=True,
        rationale="",
    )

    mock_papers = MagicMock()
    mock_papers.run.return_value = PapersResult()
    tool._papers_module = mock_papers
    tool._code_module = MagicMock()
    tool._web_module = MagicMock()
    tool._synthesis_agent.synthesise.return_value = _make_result()

    result = tool.execute(
        query="test",
        context="",
        sources=["papers"],
        budget_tokens=2_000_000,  # over cap
    )
    assert result.budget_warning is not None
    assert "1,000,000" in result.budget_warning


def test_execute_returns_research_result():
    tool = ResearchTool.__new__(ResearchTool)
    tool._jobs = MagicMock()

    from app.harness.research.types import RoutePlan
    tool._routing_agent = MagicMock()
    tool._routing_agent.route.return_value = RoutePlan(
        modules=["papers"],
        sub_queries={"papers": "calibration"},
        budgets={"papers": 150_000},
        parallel_ok=True,
        rationale="",
    )
    tool._papers_module = MagicMock()
    tool._papers_module.run.return_value = PapersResult()
    tool._code_module = MagicMock()
    tool._web_module = MagicMock()
    tool._synthesis_agent = MagicMock()
    tool._synthesis_agent.synthesise.return_value = _make_result("calibration summary")

    result = tool.execute(query="calibration", context="", sources=["papers"], budget_tokens=150_000)
    assert result.summary == "calibration summary"


def test_start_returns_job_id():
    tool = ResearchTool.__new__(ResearchTool)
    tool._jobs = MagicMock()
    tool._jobs.create.return_value = "job-123"
    tool._routing_agent = MagicMock()
    tool._synthesis_agent = MagicMock()
    tool._papers_module = MagicMock()
    tool._code_module = MagicMock()
    tool._web_module = MagicMock()

    payload = tool.start(query="test", context="", sources=["papers"], budget_tokens=50_000)
    assert payload["job_id"] == "job-123"
    assert "estimated_seconds" in payload


def test_get_delegates_to_registry():
    tool = ResearchTool.__new__(ResearchTool)
    tool._jobs = MagicMock()
    tool._jobs.get.return_value = {"status": "running", "progress": {}}

    result = tool.get("job-abc")
    assert result["status"] == "running"
    tool._jobs.get.assert_called_once_with("job-abc")


def test_handler_research_dispatches_execute():
    tool = ResearchTool.__new__(ResearchTool)
    tool.execute = MagicMock(return_value=_make_result())
    import dataclasses
    result = tool.handle_research({"query": "test", "sources": ["papers"]})
    tool.execute.assert_called_once()
    assert result["summary"] == "done"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_tool.py -v 2>&1 | tail -8
```

- [ ] **Step 3: Write tool.py**

Create `backend/app/harness/research/tool.py`:

```python
from __future__ import annotations

import dataclasses
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.harness.clients.base import ToolSchema
from app.harness.research.jobs import JobRegistry
from app.harness.research.modules.code import CodeModule
from app.harness.research.modules.papers import PapersModule
from app.harness.research.modules.web import WebModule
from app.harness.research.router import RoutingAgent
from app.harness.research.synthesis import SynthesisAgent
from app.harness.research.types import (
    CodeResult,
    PapersResult,
    ResearchResult,
    RoutePlan,
    WebResult,
)

logger = logging.getLogger(__name__)

_BUDGET_HARDCAP = 1_000_000
_BUDGET_WARNING = (
    "Requested budget exceeded 1,000,000 tokens (the hard cap). "
    "Research ran at 1,000,000 tokens. To raise the cap, ask a developer."
)

# Estimated seconds per source module (rough heuristic for job ETA)
_MODULE_ESTIMATE_S = {"papers": 30, "code": 15, "web": 10}


def _build_anthropic_client() -> Any:
    import anthropic
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


RESEARCH_SCHEMAS: tuple[ToolSchema, ...] = (
    ToolSchema(
        name="research",
        description=(
            "Run a synchronous research query across papers, code, and/or web sources. "
            "Returns structured findings including papers, code examples, and a summary. "
            "Use when the result is needed before your next step. "
            "For queries that will take >60s (deep citation crawls, many sources), "
            "prefer research_start so you can do other work in parallel.\n\n"
            "budget_tokens controls total token spend across all modules. "
            "Default 150,000 (50k per module). The routing agent allocates the budget "
            "across modules based on your query — you can skew allocation by setting a "
            "higher total (e.g. 300,000 for a deep paper crawl). "
            "Hard cap: 1,000,000 tokens. Requests above the cap run at 1M and return "
            "a budget_warning field — contact a developer to raise the cap."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to research. Be specific — include the domain, method name, "
                        "metric, dataset, or constraint. "
                        "Bad: 'calibration'. "
                        "Good: 'isotonic regression calibration for imbalanced binary "
                        "classification, LightGBM, post-hoc'."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Optional. Relevant context from prior work that narrows the search — "
                        "e.g. findings from a previous research call, dataset characteristics, "
                        "or constraints already established."
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["papers", "code", "web"]},
                    "description": "Which source modules to run. Omit for all three.",
                },
                "budget_tokens": {
                    "type": "integer",
                    "description": (
                        "Total token budget across all modules. Default 150,000. "
                        "Increase for deeper research. Hard cap 1,000,000."
                    ),
                },
            },
            "required": ["query"],
        },
    ),
    ToolSchema(
        name="research_start",
        description=(
            "Start a research query in the background and return a job_id immediately. "
            "Use when you have other analysis, tool calls, or user interaction to do "
            "while research runs. Retrieve results with research_get.\n\n"
            "Same budget_tokens semantics as research — default 150,000, hard cap 1,000,000."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "context": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["papers", "code", "web"]},
                },
                "budget_tokens": {"type": "integer"},
            },
            "required": ["query"],
        },
    ),
    ToolSchema(
        name="research_get",
        description=(
            "Fetch the result of a research_start job. Non-blocking — returns immediately "
            "with whatever has completed so far. "
            "Check the status field: 'running' = partial results only, "
            "'done' = full result available, 'failed' = retry with research synchronously, "
            "'not_found' = job expired or invalid."
        ),
        input_schema={
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
        },
    ),
)


class ResearchTool:
    """Orchestrates RoutingAgent → module execution → SynthesisAgent."""

    def __init__(self) -> None:
        api = _build_anthropic_client()
        self._routing_agent = RoutingAgent(api_client=api)
        self._synthesis_agent = SynthesisAgent(api_client=api)
        self._papers_module = PapersModule()
        self._code_module = CodeModule()
        self._web_module = WebModule()
        self._jobs = JobRegistry()

    # ── Public execute / start / get ─────────────────────────────────────────

    def execute(
        self,
        query: str,
        context: str,
        sources: list[str],
        budget_tokens: int,
    ) -> ResearchResult:
        budget_warning: str | None = None
        if budget_tokens > _BUDGET_HARDCAP:
            budget_warning = _BUDGET_WARNING
            budget_tokens = _BUDGET_HARDCAP

        sources = sources or ["papers", "code", "web"]
        t0 = time.monotonic()

        plan = self._routing_agent.route(
            query=query, context=context,
            sources=sources, budget_tokens=budget_tokens,
        )

        papers, code, web = self._run_modules(plan, query)
        total_ms = int((time.monotonic() - t0) * 1000)

        return self._synthesis_agent.synthesise(
            query=query, context=context,
            papers=papers, code=code, web=web,
            modules_ran=plan.modules,
            total_ms=total_ms,
            budget_tokens_used=budget_tokens,
            budget_warning=budget_warning,
        )

    def start(
        self,
        query: str,
        context: str,
        sources: list[str],
        budget_tokens: int,
    ) -> dict[str, Any]:
        sources = sources or ["papers", "code", "web"]
        est = sum(_MODULE_ESTIMATE_S.get(s, 20) for s in sources)
        job_id = self._jobs.create(query=query, sources=sources, estimated_seconds=est)

        def _run() -> None:
            try:
                result = self.execute(query, context, sources, budget_tokens)
                self._jobs.complete(job_id, result)
            except Exception as exc:
                logger.error("Research job %s failed: %s", job_id, exc)
                self._jobs.fail(job_id, str(exc))

        threading.Thread(target=_run, daemon=True).start()
        return {"job_id": job_id, "estimated_seconds": est}

    def get(self, job_id: str) -> dict[str, Any]:
        return self._jobs.get(job_id)

    # ── Tool handlers (called by ToolDispatcher) ──────────────────────────────

    def handle_research(self, args: dict[str, Any]) -> dict[str, Any]:
        result = self.execute(
            query=args["query"],
            context=args.get("context", ""),
            sources=args.get("sources", ["papers", "code", "web"]),
            budget_tokens=int(args.get("budget_tokens", 150_000)),
        )
        return dataclasses.asdict(result)

    def handle_research_start(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.start(
            query=args["query"],
            context=args.get("context", ""),
            sources=args.get("sources", ["papers", "code", "web"]),
            budget_tokens=int(args.get("budget_tokens", 150_000)),
        )

    def handle_research_get(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.get(args["job_id"])

    # ── Internal module dispatch ──────────────────────────────────────────────

    def _run_modules(
        self, plan: RoutePlan, original_query: str,
    ) -> tuple[PapersResult, CodeResult, WebResult]:
        papers = PapersResult()
        code = CodeResult()
        web = WebResult()

        def run_papers() -> PapersResult:
            q = plan.sub_queries.get("papers", original_query)
            b = plan.budgets.get("papers", 50_000)
            return self._papers_module.run(q, b)

        def run_code() -> CodeResult:
            q = plan.sub_queries.get("code", original_query)
            b = plan.budgets.get("code", 30_000)
            return self._code_module.run(q, b)

        def run_web() -> WebResult:
            b = plan.budgets.get("web", 20_000)
            urls = [plan.sub_queries.get("web", "")] if plan.sub_queries.get("web") else []
            return self._web_module.run(urls, b) if urls else WebResult()

        module_fns = {
            "papers": run_papers,
            "code": run_code,
            "web": run_web,
        }

        if plan.parallel_ok and len(plan.modules) > 1:
            with ThreadPoolExecutor(max_workers=3) as ex:
                futures = {ex.submit(module_fns[m]): m for m in plan.modules if m in module_fns}
                for fut in as_completed(futures):
                    mod = futures[fut]
                    try:
                        result = fut.result()
                        if mod == "papers":
                            papers = result
                        elif mod == "code":
                            code = result
                        elif mod == "web":
                            web = result
                    except Exception as exc:
                        logger.warning("Module %s failed: %s", mod, exc)
        else:
            for mod in plan.modules:
                fn = module_fns.get(mod)
                if fn is None:
                    continue
                try:
                    result = fn()
                    if mod == "papers":
                        papers = result
                    elif mod == "code":
                        code = result
                    elif mod == "web":
                        web = result
                except Exception as exc:
                    logger.warning("Module %s failed: %s", mod, exc)

        return papers, code, web
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_tool.py -v 2>&1 | tail -15
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/research/tool.py backend/app/harness/research/tests/test_tool.py
git commit -m "feat(research): ResearchTool — orchestrator with sync/async variants"
```

---

## Task 9: Wire into dispatcher + PARALLEL_SAFE_TOOLS

**Files:**
- Modify: `backend/app/harness/skill_tools.py` (add `register_research_tools()`)
- Modify: `backend/app/harness/loop.py` (add `"research"` to `PARALLEL_SAFE_TOOLS`)

- [ ] **Step 1: Write test for registration**

Add to `backend/app/harness/research/tests/test_tool.py` (append at end of file):

```python
def test_register_research_tools_adds_three_handlers():
    from app.harness.dispatcher import ToolDispatcher
    from app.harness.research.tool import register_research_tools

    disp = ToolDispatcher()
    register_research_tools(disp)

    assert disp.has("research")
    assert disp.has("research_start")
    assert disp.has("research_get")
```

- [ ] **Step 2: Run — expect NameError (function doesn't exist yet)**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_tool.py::test_register_research_tools_adds_three_handlers -v 2>&1 | tail -8
```

- [ ] **Step 3: Add register_research_tools to tool.py**

Append to `backend/app/harness/research/tool.py`:

```python

# ── Process-wide singleton ────────────────────────────────────────────────────

_research_tool: ResearchTool | None = None
_tool_lock = threading.Lock()


def get_research_tool() -> ResearchTool:
    global _research_tool
    if _research_tool is not None:
        return _research_tool
    with _tool_lock:
        if _research_tool is None:
            _research_tool = ResearchTool()
    return _research_tool


def register_research_tools(dispatcher: Any) -> None:
    """Register research, research_start, research_get with the dispatcher."""
    tool = get_research_tool()
    dispatcher.register("research", tool.handle_research)
    dispatcher.register("research_start", tool.handle_research_start)
    dispatcher.register("research_get", tool.handle_research_get)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/tests/test_tool.py::test_register_research_tools_adds_three_handlers -v 2>&1 | tail -8
```

- [ ] **Step 5: Add import and call in skill_tools.py**

In `backend/app/harness/skill_tools.py`, at the bottom of `register_core_tools()`, add:

```python
    # Research tools (papers, code, web) — parallel-safe read-only
    from app.harness.research.tool import register_research_tools  # noqa: PLC0415
    register_research_tools(dispatcher)
```

- [ ] **Step 6: Add "research" to PARALLEL_SAFE_TOOLS in loop.py**

In `backend/app/harness/loop.py`, find:

```python
PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset({
    "skill",
    "read_file",
    "glob_files",
    "search_text",
    "session_search",
    "get_artifact",
    "get_context_status",
})
```

Replace with:

```python
PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset({
    "skill",
    "read_file",
    "glob_files",
    "search_text",
    "session_search",
    "get_artifact",
    "get_context_status",
    "research",          # sync research is read-only; safe to run alongside other reads
    "research_get",      # non-blocking poll; always read-only
})
```

- [ ] **Step 7: Run full test suite**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/ app/harness/tests/test_loop.py -v 2>&1 | tail -20
```

Expected: all pass, no regressions in loop tests.

- [ ] **Step 8: Commit**

```bash
git add backend/app/harness/skill_tools.py backend/app/harness/loop.py backend/app/harness/research/tool.py backend/app/harness/research/tests/test_tool.py
git commit -m "feat(research): wire into ToolDispatcher + PARALLEL_SAFE_TOOLS"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run all research tests**

```bash
cd backend && .venv/bin/python -m pytest app/harness/research/ -v 2>&1 | tail -25
```

Expected: all pass.

- [ ] **Step 2: Run mypy on new files**

```bash
cd backend && .venv/bin/python -m mypy app/harness/research/ --ignore-missing-imports 2>&1 | tail -20
```

Fix any type errors before proceeding.

- [ ] **Step 3: Run ruff**

```bash
cd backend && .venv/bin/python -m ruff check app/harness/research/ --fix 2>&1 | tail -10
```

- [ ] **Step 4: Smoke-test import chain**

```bash
cd backend && .venv/bin/python -c "
from app.harness.research.tool import RESEARCH_SCHEMAS, ResearchTool
from app.harness.research.types import ResearchResult
print('schemas:', [s.name for s in RESEARCH_SCHEMAS])
print('import ok')
" 2>&1
```

Expected:
```
schemas: ['research', 'research_start', 'research_get']
import ok
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(research): complete research tool — papers/code/web modules, routing, synthesis, async jobs"
```
