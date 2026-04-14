# Gap Analysis: claude-code-agent vs Reference Implementations

**Date:** 2026-04-14
**Scope:** claude-code-agent (primary) vs Analytical-chatbot (web peer) and claude-code-main (CLI reference)

---

## 1. Executive Summary

`claude-code-agent` is a purpose-built analytical platform for data scientists, with a sophisticated harness, a tiered skill system, and unique infrastructure for context visibility and artifact management. Compared to `Analytical-chatbot` (a simpler LangGraph peer) and `claude-code-main` (the full Claude Code CLI), the agent holds structural advantages in eval depth, data infrastructure, and context transparency. The primary gaps are operational: the ContextManager is not yet scoped per session, there is no persistent memory across sessions, no hook system, and the tool surface is narrower than what data scientists need for exploratory work. Closing those four gaps would bring the agent to parity with both references while preserving its unique strengths.

---

## 2. Scope

**Included:**
- Memory and context management
- Agent harness and loop mechanics
- Skill and tool systems
- Streaming and artifact handling
- Eval and trace infrastructure

**Excluded (not relevant for single data-scientist use case):**
- MCP server integration
- Multi-user session isolation (beyond the ContextManager gap)
- Authentication / login flows
- Deployment and scaling infrastructure

---

## 3. Memory Layer

### Comparison Table

| Feature | claude-code-agent | Analytical-chatbot | claude-code-main |
|---|---|---|---|
| In-session message history | Yes (turn buffer) | Yes (LangGraph state) | Yes (API messages list) |
| Cross-session persistent memory | No | No | Yes — file-based (MEMORY.md, user.md, feedback.md, project.md, reference.md) |
| Memory types | None | None | Typed: user preferences, project context, feedback history, reference facts |
| Memory write mechanism | None | None | `save-session` skill + file writes |
| Memory read mechanism | None | None | Files injected as system prompt context at session start |
| Findings / notes persistence | No | No | Yes (project.md, reference.md) |
| Cross-session continuity | No — every session starts cold | No — every session starts cold | Yes — recalled automatically |

### Narrative

This is the most impactful gap for a working data scientist. `claude-code-main` implements file-based persistent memory with typed categories: `user.md` stores preferences, `project.md` stores project context, `feedback.md` stores correction history, and `reference.md` stores facts the model should always recall. These files are injected at session start so the agent "remembers" prior analysis decisions, preferred chart styles, dataset schemas already profiled, and analyst-specific conventions.

For a data scientist running iterative analysis over days or weeks, cold-start sessions are a meaningful friction point. Every session requires re-establishing context: what datasets are loaded, what hypotheses were rejected, what the preferred grouping columns are. Neither `claude-code-agent` nor `Analytical-chatbot` addresses this. The fix is a memory store scoped to the analyst's workspace, with writes triggered at session end and reads injected into the PreTurnInjector at session start.

Key files in claude-code-main: `~/.claude/MEMORY.md`, `~/.claude/projects/<path>/memory/`

---

## 4. Context Tracking

### Comparison Table

| Feature | claude-code-agent | Analytical-chatbot | claude-code-main |
|---|---|---|---|
| Explicit context layer tracking | Yes — ContextLayer objects (name, tokens, compactable, items) | No | No |
| Compaction history | Yes — before/after token counts, information loss tracking | No | API-native (opaque) |
| Context composition visibility | Yes — per-layer breakdown available at any point | No | No |
| Compactable layer marking | Yes — layers flagged as safe to compact | No | No |
| Context budget enforcement | Yes — PreTurnInjector reads layer state | No | Implicit via API limits |
| Per-session isolation | No — ContextManager is currently global | N/A | N/A |
| Trace bus publication | Yes — context events published to trace bus | No | No |
| Token counting granularity | Per-layer | Total only (LangGraph) | API-reported total |

### Narrative

The ContextManager is `claude-code-agent`'s most architecturally distinctive component and also its most urgent bug. The design — tracking named ContextLayer objects with token counts, compactability flags, and compaction history — gives the agent something neither reference has: precise visibility into what is consuming context and what has been lost to compaction. This is invaluable for a data scientist running long multi-step analyses where context pressure accumulates.

The problem is that the ContextManager is currently a global singleton. When multiple sessions run (even sequentially in some configurations), layers bleed across session boundaries. This is a correctness issue, not just a design smell. The fix is to scope the ContextManager instance to the session lifecycle — instantiated at session start, torn down at session end, with state accessible via the session ID.

`Analytical-chatbot` relies entirely on LangGraph's internal message management and has no visibility into token composition. `claude-code-main` delegates to the Anthropic API's native compaction, which is opaque — the model handles it, but the application cannot inspect what was compacted or track information loss.

Once the per-session scoping is fixed, the ContextManager becomes a genuine competitive advantage rather than a liability.

Key file: `backend/app/context_manager.py` (inferred path based on harness structure)

---

## 5. Harness & Agent Loop

### Comparison Table

| Feature | claude-code-agent | Analytical-chatbot | claude-code-main |
|---|---|---|---|
| Core loop | AgentLoop with structured phases | LangGraph graph execution | Native API streaming loop |
| Pre-turn injection | Yes — PreTurnInjector (context, skills, system prompt assembly) | No explicit equivalent | System prompt rebuilt each turn |
| Turn wrap-up | Yes — TurnWrapUp (artifact processing, trace flushing) | No explicit equivalent | No explicit equivalent |
| Model routing | Yes — ModelRouter (route by task type or cost) | No | No — single model per session |
| Tool dispatch | Yes — ToolDispatcher with registry | LangGraph tool nodes | Built-in tool registry |
| Sandboxed execution | Yes — SandboxExecutor | Yes — Python sandbox | No (Bash tool runs on host) |
| Hook system (pre/postToolUse) | No | No | Yes — shell commands execute per tool event, configurable in settings.json |
| Planning mode | No | No | Yes — EnterPlanMode / ExitPlanMode tool |
| Task management | No | No | Yes — TaskCreate / TaskUpdate / TaskStop / TaskList / TaskGet |
| A2A delegation | Yes — delegate_subagent in thread pool | Yes — subagent_* events | Yes — Agent tool |
| SSE streaming | Yes — 8 event types | Yes — 15+ event types | No (terminal output) |
| Eval / trace system | Yes — 5-level, judge, rubric grading | No | No |

### Narrative

The harness is the strongest structural element in `claude-code-agent`. The PreTurnInjector / TurnWrapUp lifecycle gives clear separation of concerns that neither reference achieves. `Analytical-chatbot` runs turns as LangGraph graph traversals — the "pre" and "post" phases exist implicitly in node ordering but are not named abstractions. `claude-code-main` rebuilds the system prompt each turn but does not have an explicit wrap-up phase.

The ModelRouter is a capability neither reference has: the ability to route specific task types (e.g., quick summarization vs. complex analysis) to different models or cost tiers. For data-science workloads where L1 skill calls (theme_config, html_tables) are cheap and L3 composition (dashboard_builder) is expensive, this routing can meaningfully reduce cost without degrading quality.

The three gaps in harness capability versus `claude-code-main` are:

1. **Hook system**: `claude-code-main` executes shell commands on preToolUse and postToolUse events, configurable in `settings.json`. This enables automation like auto-formatting outputs, logging tool calls to external systems, or enforcing pre-conditions before destructive operations. The agent has no equivalent.

2. **Planning mode**: `claude-code-main` has EnterPlanMode / ExitPlanMode tools that shift the agent into a structured planning phase before execution. For complex multi-step analyses, this is valuable — the analyst can review the plan before any code runs. The agent proceeds directly to execution.

3. **Task management**: `claude-code-main` has persistent task tracking within and across turns (TaskCreate, TaskUpdate, TaskStop, TaskList). Long analyses (profiling → hypothesis generation → modeling → report) benefit from a task list that tracks which steps are complete, which are in-progress, and what the next action is. The agent has no equivalent within-session task state.

---

## 6. Skills System

### Comparison Table

| Feature | claude-code-agent | Analytical-chatbot | claude-code-main |
|---|---|---|---|
| Skill system | Yes — 13 Python skills in 3 levels | No | Yes — SKILL.md markdown files |
| Skill levels / tiers | L1 primitives, L2 analytical, L3 composition | N/A | No tiers |
| Skill manifest | Yes — manifest.py with dependency graph | N/A | No manifest |
| Dependency tracking | Yes — explicit DAG between skills | N/A | No |
| Breaking change detection | Yes — manifest versioning | N/A | No |
| Skill loading mechanism | Registered at startup, dispatched by ToolDispatcher | N/A | Loaded via ToolSearch at runtime (on-demand) |
| Skill discovery | Static registry | N/A | Dynamic — ToolSearch queries skill index |
| L1 skills | theme_config, altair_charts, html_tables, data_profiler, sql_builder | Partial equivalent in ad-hoc tool calls | None (CLI context) |
| L2 skills | correlation, group_compare, time_series, stat_validate, distribution_fit | None | None |
| L3 skills | analysis_plan, report_builder, dashboard_builder | Partial (dashboard endpoint) | None |
| Domain specificity | High — data science primitives | Low — general purpose | Very high — software development |

### Narrative

The skill system is purpose-built for data science and has no meaningful equivalent in `Analytical-chatbot`. The three-level hierarchy — primitives, analytical, composition — mirrors the actual structure of analytical work: you call `data_profiler` (L1) to understand a dataset, `correlation` (L2) to test a hypothesis, and `dashboard_builder` (L3) to synthesize results. The L3 skills orchestrate L1 and L2 skills with known dependency chains tracked in `manifest.py`.

`claude-code-main` has a skill system but it is entirely different in kind: SKILL.md files are markdown documents loaded at runtime via ToolSearch. They are guidance documents, not executable code. The agent's Python skills are callable functions with defined inputs, outputs, and failure modes. This is a stronger contract.

The breaking change detection in the manifest is forward-looking infrastructure that neither reference has. As the skill library grows, the manifest prevents L3 composition skills from silently failing when an L1 dependency changes its output schema.

One gap versus `claude-code-main`: skill discovery is static in the agent (registered at startup) while `claude-code-main` uses dynamic ToolSearch to load skills on demand from an index. For a skill library that grows to 30–50 skills, dynamic discovery avoids loading everything into the context on every turn.

---

## 7. Tools

### Comparison Table

| Feature | claude-code-agent | Analytical-chatbot | claude-code-main |
|---|---|---|---|
| execute_python (sandbox) | Yes | Yes | No (Bash runs on host) |
| write_working (scratchpad) | Yes | Implicit in LangGraph state | No direct equivalent |
| delegate_subagent (A2A) | Yes | Yes (subagent_* events) | Yes (Agent tool) |
| File system: read | No | No | Yes — Read, Glob |
| File system: write | No | No | Yes — Write, Edit |
| File system: search | No | No | Yes — Grep, Glob |
| Shell execution | No | No | Yes — Bash |
| Web fetch | No | No | Yes — WebFetch |
| Web search | No | No | Yes — WebSearch |
| DuckDB / SQL | Yes (per-session DuckDB) | Yes (DuckDB) | No |
| Dataset registry | Yes | Partial | No |
| Schema awareness | Yes | No | No |
| Notebook tools | No | No | Yes — NotebookEdit |
| Task tools | No | No | Yes — TaskCreate/Update/Stop/List/Get |
| Schedule / cron | No | No | Yes — ScheduleWakeup, CronCreate |

### Narrative

The tool gap is most visible for exploratory data science workflows. A data scientist frequently needs to:

- **Read local files**: load a CSV from disk, inspect a config file, read a schema definition. The agent has no file-system read tools; the analyst must paste content or use the Python sandbox.
- **Write outputs**: save a processed dataset to disk, export a report as a file. Again, no native file write tool — the Python sandbox can do this but it is indirect.
- **Fetch external data**: pull from a REST API, download a reference dataset, read a data dictionary URL. No WebFetch tool.

`claude-code-main` has a comprehensive tool surface for software development (Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch) that maps well onto data-science file operations. Adding a subset — Read, Write, Glob, WebFetch — to the agent's ToolDispatcher would close the most impactful gaps without adding complexity.

The agent's DuckDB per-session database and dataset registry are genuine advantages (see section 9). The sandbox execution environment is also an advantage over `claude-code-main`'s host-level Bash execution: the analyst's environment is isolated, so a runaway query or accidental `rm` does not affect the host.

---

## 8. Priority Gaps to Close

Ranked by data-scientist impact:

### 1. Per-Session ContextManager (Critical Correctness Issue)

**Current state:** ContextManager is a global singleton. Layer state bleeds across sessions.
**Impact:** Incorrect token accounting, potential context poisoning between sessions.
**Fix:** Instantiate ContextManager per session ID. Pass session-scoped instance through AgentLoop. Tear down at session end.
**Effort:** Medium — refactor to dependency-inject the manager rather than import as global.
**Reference:** Neither reference has this gap — they avoid it by not having a ContextManager at all, but the agent's design requires it to be correct.

### 2. Persistent Memory for Findings and Notes

**Current state:** Every session starts cold. No recall of prior analysis, preferences, or dataset knowledge.
**Impact:** High friction for iterative multi-session work. Analyst re-establishes context every time.
**Fix:** Implement a file-based memory store (analyst workspace directory). Write at session end via TurnWrapUp. Read at session start via PreTurnInjector. Types: `workspace.md` (active project context), `findings.md` (confirmed hypotheses, rejected ones), `preferences.md` (chart styles, grouping columns, preferred models).
**Effort:** Medium — the injection point (PreTurnInjector) already exists.
**Reference:** `claude-code-main` — `~/.claude/projects/<path>/memory/` pattern.

### 3. Hook System for Pre/PostToolUse Automation

**Current state:** No hook mechanism. Tool calls execute with no surrounding automation.
**Impact:** Cannot enforce pre-conditions, cannot log tool calls externally, cannot auto-post-process outputs.
**Fix:** Add hook registration to ToolDispatcher. Execute registered shell commands or Python callables before and after each tool invocation. Configurable per tool name or tool type.
**Effort:** Medium — ToolDispatcher already wraps all tool calls; hook execution slots in naturally.
**Reference:** `claude-code-main` settings.json `hooks` config: `{ "PostToolUse": [{ "matcher": "execute_python", "command": "..." }] }`.

### 4. Expanded Tool Set (File System + Web Fetch)

**Current state:** Three tools: execute_python, write_working, delegate_subagent.
**Impact:** File-based workflows require workarounds through the Python sandbox.
**Fix:** Add Read (file read), Write (file write), Glob (file search), WebFetch (URL fetch) to the ToolDispatcher registry. Scope file tools to the analyst's workspace directory for safety.
**Effort:** Low-to-medium per tool — the sandbox and dispatcher patterns are established.
**Reference:** `claude-code-main` — Read, Write, Edit, Glob, Bash, WebFetch, WebSearch.

### 5. Within-Session Task Tracking

**Current state:** No task state. Long multi-step analyses (profile → hypothesize → model → report) have no structured progress tracking.
**Impact:** The agent and analyst lose track of which steps are done in long sessions. No ability to resume a partially-complete analysis plan.
**Fix:** Add lightweight task objects to session state (name, status, dependencies). Expose via a task_status tool. Update task state in TurnWrapUp after each completed step.
**Effort:** Medium — requires session state object and a new tool.
**Reference:** `claude-code-main` — TaskCreate / TaskUpdate / TaskStop / TaskList / TaskGet.

---

## 9. Competitive Advantages

Areas where `claude-code-agent` outperforms both references:

### Context Visibility (Unique Architecture)

Neither `Analytical-chatbot` nor `claude-code-main` can tell you what is consuming context or what was lost to compaction. The ContextManager tracks named layers (system prompt, skill manifests, conversation history, artifact summaries) with token counts and compaction history including before/after counts and information loss flags. Once the per-session scoping issue is fixed, this becomes a first-class debugging and monitoring capability with no equivalent in the reference implementations.

The trace bus publication of context events also means compaction decisions are observable and auditable — critical for understanding why an analysis went wrong after a long session.

### Eval Framework (5-Level, Judge, Rubric)

Neither reference has a structured evaluation framework. `claude-code-agent` has a 5-level eval system with a judge model, rubric-based grading, and trace infrastructure for recording and replaying evaluations. For a data-science platform where output quality (chart accuracy, statistical correctness, report coherence) matters, this is foundational infrastructure. `Analytical-chatbot` has no eval. `claude-code-main` has no eval specific to its outputs.

### Data Infrastructure (DuckDB + Dataset Registry + Schema Awareness)

The per-session DuckDB database, dataset registry, and schema awareness give the agent deep integration with the analyst's data. SQL queries run against actual loaded data; the skill system knows column types and cardinalities when choosing chart types or statistical tests. `claude-code-main` has no data infrastructure — it is a code tool. `Analytical-chatbot` has DuckDB but no registry or schema awareness layer.

Key path: the dataset management and DuckDB session isolation described in `docs/superpowers/` and referenced in `duckdb-wal-sandbox-isolation` skill.

### Artifact Distillation (Context-Lean by Design)

The ArtifactStore design is architecturally sound: artifacts (charts, tables) are stored in SQLite with disk overflow and are **not** placed in the model context. Instead, distilled text summaries are injected. This keeps context lean as the number of artifacts grows — a critical property for long analytical sessions that generate dozens of intermediate charts and tables.

`Analytical-chatbot` stores artifact IDs in messages but the rendering path is tightly coupled to the frontend. `claude-code-main` has no artifact system. The distillation approach in `claude-code-agent` is the right pattern and should be preserved as the skill library grows.

### Skill Dependency Graph (manifest.py)

The manifest with explicit skill dependencies and breaking change detection has no equivalent in either reference. As the skill library grows from 13 to 30+ skills, the DAG prevents silent failures when upstream primitives change. `claude-code-main`'s SKILL.md files are documentation with no machine-readable dependency structure. This is infrastructure the agent should invest in, not abandon.

### SSE Streaming Transparency

The 8 SSE event types — `turn_start`, `tool_call`, `tool_result`, `scratchpad_delta`, `a2a_end`, `turn_end`, `error`, `artifact` — give the frontend complete visibility into agent state. Every tool invocation is visible in real time, including sandbox executions, subagent delegations, and artifact completions. `Analytical-chatbot` has more event types (15+) but many are UI-specific (inline_component, suggestions) rather than harness-transparency events. `claude-code-main` has no SSE (terminal output only). The agent's streaming design is well-suited to the web UI use case and should be extended, not replaced.

---

## 10. Conclusion

`claude-code-agent` has the right foundations for a professional data-science analytical platform: a structured harness, a tiered skill system with dependency tracking, artifact distillation that keeps context lean, a unique context visibility layer, and a 5-level eval framework. The five priority gaps — per-session ContextManager scoping, persistent memory, hook system, expanded file/web tools, and within-session task tracking — are all additive changes that fit naturally into the existing architecture. None require architectural rethinking. Closing these gaps, particularly the ContextManager scoping (a correctness issue) and persistent memory (the highest analyst-facing friction), would bring the agent to or above parity with both reference implementations while preserving the advantages it already holds.
