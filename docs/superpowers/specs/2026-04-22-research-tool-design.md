# Research Tool — Design Spec

**Date:** 2026-04-22  
**Status:** Approved for implementation  
**Scope:** `backend/app/harness/research/`

---

## Problem

The main agent has no way to ground its analysis in current literature, working code examples, or recent ML developments. When a user asks for the "best approach" to calibration, forecasting, or any methodology question, the agent works from training knowledge only — it cannot crawl papers, traverse citation graphs, or find validated implementations.

---

## Solution

A modular **research tool** that the main agent calls as a black box. Internally it runs a coordinator–specialist architecture: a cheap routing LLM decides which source modules to run and with what sub-queries, the modules execute (in parallel when possible), and a cheap synthesis LLM merges the outputs into a structured result.

The main agent gets three tool variants and **chooses** which to use based on context:

| Tool | When to use |
|------|-------------|
| `research` | Synchronous — result needed before next step |
| `research_start` | Async — main agent has parallel work to do |
| `research_get` | Fetch result from a started job (partial if still running) |

All three share the same execution engine. Switching costs one word in the tool call.

---

## Architecture

```
Main agent
  │  research(query, context, sources, budget_tokens=150_000)        ← sync
  │  research_start(query, context, sources, budget_tokens=150_000)  ← async, returns job_id
  │  research_get(job_id)                                            ← poll / collect
  ▼
ResearchTool.execute(budget_tokens)
  │  clamp: if budget_tokens > 1_000_000 → use 1_000_000, set budget_warning flag
  │  emits StreamEvent("research_start", {query, sources, budget_tokens})
  ▼
RoutingAgent  [haiku-class LLM, ~500 tokens in/out]
  │  input:  query + context + total_budget + available_sources
  │  output: {modules_to_run, sub_queries{}, budgets{}, parallel_ok: bool}
  │  emits StreamEvent("research_routing", {plan})
  ▼
ThreadPoolExecutor  (when parallel_ok)
  ├── PapersModule(sub_query, budget_tokens=<from_router>)
  │     emits StreamEvent("research_progress", {module:"papers", step, found_count})
  │     returns PapersResult
  ├── CodeModule(sub_query, budget_tokens=<from_router>)
  │     emits StreamEvent("research_progress", {module:"code", step, found_count})
  │     returns CodeResult
  └── WebModule(sub_query, budget_tokens=<from_router>)
        emits StreamEvent("research_progress", {module:"web", step, found_count})
        returns WebResult
  ▼
SynthesisAgent  [haiku-class LLM, ~2k tokens in/out]
  │  merges module results into structured output
  │  emits StreamEvent("research_done", {modules_ran, total_ms})
  ▼
ResearchResult
  {summary, papers[], code_examples[], web_refs[], follow_up_questions[],
   budget_warning?}   ← set if caller requested > 1M tokens
```

**Sync path:** `ResearchTool.execute()` returns `ResearchResult` directly.  
**Async path:** `ResearchTool.start()` submits to `JobRegistry`, returns `{job_id, estimated_seconds}` immediately. Background thread calls `execute()`. `ResearchTool.get(job_id)` returns partial results if still running.

---

## Tool Schemas

### `research`
```json
{
  "name": "research",
  "description": "Run a synchronous research query across papers, code, and/or web sources. Returns structured findings including papers, code examples, and a summary. Use when the result is needed before your next step. For queries that will take >60s (deep citation crawls, many sources), prefer research_start so you can do other work in parallel.\n\nbudget_tokens controls total token spend across all modules. Default 150,000 (50k per module). The routing agent allocates the budget across modules based on your query — you can skew allocation by setting a higher total (e.g. 300,000 for a deep paper crawl). Hard cap: 1,000,000 tokens. Requests above the cap run at 1M and return a budget_warning field — contact a developer to raise the cap.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "What to research. Be specific — include the domain, method name, metric, dataset, or constraint. Bad: 'calibration'. Good: 'isotonic regression calibration for imbalanced binary classification, LightGBM, post-hoc'."
      },
      "context": {
        "type": "string",
        "description": "Optional. Relevant context from prior work that narrows the search — e.g. findings from a previous research call, the user's dataset characteristics, or constraints already established."
      },
      "sources": {
        "type": "array",
        "items": {"type": "string", "enum": ["papers", "code", "web"]},
        "default": ["papers", "code", "web"],
        "description": "Which source modules to run. Omit for all three. Use ['papers'] for literature-only, ['code'] for implementation-only."
      },
      "budget_tokens": {
        "type": "integer",
        "default": 150000,
        "description": "Total token budget across all modules. Default 150,000. The routing agent allocates this across the modules you requested. Increase for deeper research (e.g. 300,000 for a full citation graph crawl). Hard cap is 1,000,000 — requests above the cap run at 1M and include a budget_warning in the result."
      }
    },
    "required": ["query"]
  }
}
```

### `research_start`
```json
{
  "name": "research_start",
  "description": "Start a research query in the background and return a job_id immediately. Use when you have other analysis, tool calls, or user interaction to do while research runs. Retrieve results with research_get.\n\nSame budget_tokens semantics as research — default 150,000, hard cap 1,000,000.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query":   {"type": "string", "description": "Same as research.query"},
      "context": {"type": "string", "description": "Same as research.context"},
      "sources": {
        "type": "array",
        "items": {"type": "string", "enum": ["papers","code","web"]},
        "default": ["papers","code","web"]
      },
      "budget_tokens": {"type": "integer", "default": 150000}
    },
    "required": ["query"]
  }
}
```

### `research_get`
```json
{
  "name": "research_get",
  "description": "Fetch the result of a research_start job. Non-blocking — returns immediately with whatever has completed so far. Check the status field: 'running' means partial results only, 'done' means full result available, 'failed' means retry with research synchronously.",
  "input_schema": {
    "type": "object",
    "properties": {
      "job_id": {"type": "string"}
    },
    "required": ["job_id"]
  }
}
```

---

## Source Modules

### PapersModule (`modules/papers.py`)

Three-source stack, priority order:

1. **HF Papers feed** (`https://huggingface.co/api/papers`) — best for recent ML (≤30 days). No API key. Used first when query contains recency signals ("recent", "new", "2024", "2025", "state of the art").

2. **Semantic Scholar** (`https://api.semanticscholar.org`) — citation graphs, high-citation search, paper details, section-by-section reading. Primary for landmark/foundational queries. Optional `S2_API_KEY` env var raises rate limits.

3. **ArXiv** (`https://export.arxiv.org/api/query`) — always-available fallback for full paper content. Used when S2 is rate-limited or a specific ArXiv ID is known.

**Operations the module can perform within its token budget:**
- Search by query (all three sources)
- Fetch paper metadata + abstract
- Traverse citation graph (S2) — downstream papers that cite the anchor
- Read specific sections (methodology, experiments, results) via ArXiv HTML
- Extract result-to-recipe mappings: "dataset X + method Y + lr Z → metric W"

**Return type:**
```python
@dataclass
class PapersResult:
    papers: list[PaperFinding]   # ranked by relevance
    crawl_depth: int             # how many hops the citation graph went

@dataclass
class PaperFinding:
    title: str
    arxiv_id: str | None
    year: int | None
    citation_count: int | None
    key_finding: str             # one sentence: what result + what recipe
    section_excerpts: list[str]  # relevant methodology/experiment quotes
    source: str                  # "hf_papers" | "semantic_scholar" | "arxiv"
```

### CodeModule (`modules/code.py`)

Uses `gh` CLI (already in environment). No additional auth needed if `GITHUB_TOKEN` is set.

**Operations:**
- `gh search code <query> --limit 20` — find relevant files
- `gh api repos/{owner}/{repo}/contents/{path}` — read file contents
- Filter by language, stars, recency

**Return type:**
```python
@dataclass
class CodeResult:
    examples: list[CodeExample]

@dataclass
class CodeExample:
    url: str
    repo: str
    file_path: str
    snippet: str       # relevant excerpt, ≤500 chars
    relevance: str     # one sentence: why this is relevant
    stars: int | None
```

### WebModule (`modules/web.py`)

Targeted fetch — not a general crawler. Takes specific URLs or search-derived URLs.

**Operations:**
- `httpx.get(url)` → strip HTML → extract relevant section
- Summarize with a small LLM call if content > 2000 chars

**Return type:**
```python
@dataclass
class WebResult:
    pages: list[WebPage]

@dataclass
class WebPage:
    url: str
    title: str
    summary: str   # ≤300 chars
```

---

## RoutingAgent

A single LLM call (haiku-class) that decides the execution plan and allocates the budget across modules.

### System prompt

Mirrors ml-intern's `RESEARCH_SYSTEM_PROMPT` style, adapted for data science / quant analytics:

```
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
- Papers crawls are expensive (citation graphs, section reads): give papers 50–70% when included
- Code search is cheap: 20–30% is usually enough
- Web fetch is cheapest: 10–20%
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
    "code": 40000,
    "web": 20000
  },
  "parallel_ok": true,
  "rationale": "one sentence explaining the routing decision"
}
```

### User prompt (template)

```
Query: {query}
Context: {context}
Available sources: {sources}
Total budget (tokens): {budget_tokens}

Route this query.
```

### Examples

**Parallel:** `"best isotonic calibration approaches for imbalanced LightGBM"` →
`parallel_ok: true`, papers gets 70% budget (citation graph crawl likely), code gets 30%.

**Sequential:** `"find Python code for the method described in Platt 1999"` →
papers first (get method name + details), then code with the specific method name,
`parallel_ok: false`.

**Papers-only:** `"what does the literature say about distribution shift in financial time series?"` →
`modules: ["papers"]`, full budget to papers, `parallel_ok: true` (one module).

---

## SynthesisAgent

A single LLM call (haiku-class) that merges module outputs.

**Input:** serialized module results + original query + context  
**Output:**
```python
@dataclass
class ResearchResult:
    summary: str                        # 2-4 sentences, direct answer to query
    papers: list[PaperFinding]          # from PapersModule
    code_examples: list[CodeExample]    # from CodeModule
    web_refs: list[WebPage]             # from WebModule
    follow_up_questions: list[str]      # what the agent should ask next if needed
    modules_ran: list[str]
    total_ms: int
    budget_tokens_used: int             # actual budget passed to modules (post-clamp)
    budget_warning: str | None          # set if caller requested > 1M tokens
```

---

## JobRegistry (`jobs.py`)

In-memory, session-scoped. No persistence.

```python
@dataclass
class Job:
    job_id: str
    status: Literal["running", "done", "failed"]
    started_at: float
    query: str
    sources: list[str]
    result: ResearchResult | None
    error: str | None
    partial: dict[str, Any]   # module results as they complete
    estimated_seconds: int
```

`research_get` returns:
```json
{
  "status": "running",
  "elapsed_seconds": 12,
  "estimated_seconds": 45,
  "progress": {"papers": "done", "code": "running", "web": "pending"},
  "partial_result": {"papers": [...]}   // whatever has finished
}
```

Completed jobs expire after 30 minutes (simple TTL check on access).

---

## SSE Events

All events flow through the existing `StreamEvent` system in `app/harness/stream_events.py`. The LLM never sees them — they are UI/observability only.

| Event type | Payload |
|-----------|---------|
| `research_start` | `{query, sources, job_id?}` |
| `research_routing` | `{modules, sub_queries, parallel_ok, rationale}` |
| `research_progress` | `{module, step, found_count, status}` |
| `research_done` | `{modules_ran, total_ms, paper_count, code_count}` |
| `research_error` | `{module, error}` |

---

## File Layout

```
backend/app/harness/research/
  __init__.py
  tool.py          ← ResearchTool: execute(), start(), get() + 3 ToolSchema defs
  router.py        ← RoutingAgent: one LLM call → execution plan
  synthesis.py     ← SynthesisAgent: one LLM call → ResearchResult
  jobs.py          ← JobRegistry: thread-safe dict + TTL expiry
  modules/
    __init__.py
    papers.py      ← PapersModule: HF Papers + Semantic Scholar + ArXiv
    code.py        ← CodeModule: gh CLI wrapper
    web.py         ← WebModule: httpx fetch + summarize
  types.py         ← PaperFinding, CodeExample, WebPage, ResearchResult, Job
  tests/
    test_router.py
    test_synthesis.py
    test_jobs.py
    test_papers.py
    test_code.py
```

**Integration point:** `app/harness/wiring.py` — register the three tool schemas and map `research` / `research_start` / `research_get` to `ResearchTool` methods.

**System prompt addition:** Three entries in the tool catalog with guidance on when to use `research` vs `research_start`.

---

## Error Handling

- **Module failure:** If one module fails, the others continue. `SynthesisAgent` receives whatever completed. Result includes `"modules_ran": ["papers"]` so the agent knows what was skipped.
- **RoutingAgent failure:** Fall back to running all requested modules with the original query, `parallel_ok: true`.
- **Rate limits (S2):** `PapersModule` catches 429s, waits up to 10s, then falls back to ArXiv.
- **Budget hardcap (1M tokens):** `ResearchTool.execute()` clamps `budget_tokens` to `min(budget_tokens, 1_000_000)` before passing to the RoutingAgent. If clamped, `ResearchResult.budget_warning` is set to `"Requested budget exceeded 1,000,000 tokens (the hard cap). Research ran at 1,000,000 tokens. To raise the cap, ask a developer."` The agent surfaces this to the user.
- **Module token budget:** Each module tracks estimated token usage via `len(text) // 4`. When within 10% of its allocated budget, the module wraps up and returns what it has — it never hard-stops mid-result, it just stops fetching new items.
- **Async job not found:** `research_get` returns `{status: "not_found"}` — agent should retry `research` synchronously.

---

## What Is Not In Scope

- Persistent job storage across server restarts
- User-facing job management UI
- Web search (as opposed to targeted web fetch) — no general crawling
- PDF parsing — ArXiv HTML is used instead
- Authentication flows for S2 (just env var, optional)
