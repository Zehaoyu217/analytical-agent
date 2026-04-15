# Gap Analysis v2: claude-code-agent — Complete State Assessment

**Date:** 2026-04-15  
**Prepared by:** Analysis session (claude-sonnet-4-6)  
**Supersedes:** `docs/gap-analysis.md` (2026-04-14, pre-v2 analysis)  
**References:** claude-code-main, openfang, deer-flow, Analytical-chatbot (all local projects)

---

## Historical Context: Prior Assessment (Early April 2026)

An earlier assessment (before the P0–P14 implementation phases) described the project as "~85% design/skeleton, ~15% implementation" with:
- Zero skill packages
- No agent loop
- No sandbox
- No wiki engine
- No chat API

**That description is outdated.** Since then, two full progressive plans (P0–P14) were executed. The project is now at ~75% implementation of its planned feature set. The A-H decomposition that came from that earlier analysis is still useful as an organizing lens:

| Subsystem | Old Status | Current Status (2026-04-15) |
|---|---|---|
| A: Core harness (AgentLoop, ToolDispatcher, SandboxExecutor, PreTurnInjector) | Not built | **BUILT** — all in `backend/app/harness/` |
| B: Skill system (13 skills, manifest, registry, load_skill) | Not built | **MOSTLY BUILT** — 13 packages exist; load_skill not wired to chat_api.py |
| C: Permissions + Hooks (guardrails, hook dispatch) | Not built | **PARTIAL** — guardrails (pre/post/end_of_turn) exist; no user-configurable hook system |
| D: Context + Compaction (ContextManager, layer writer, compaction engine) | Not built | **PARTIAL** — ContextManager tracks layers; no compaction engine, no tokenizer |
| E: Memory & Session (wiki engine, working.md, session notes, findings) | Not built | **PARTIAL** — wiki engine built; working.md injected; no cross-session memory |
| F: Task system (TaskCreate/Update/Stop/List) | Not built | **NOT BUILT** |
| G: MCP client | Not built | **NOT BUILT** (MCP explorer server exists, not a client) |
| H: UX services (AgentSummary, PromptSuggestion, Tips) | Not built | **NOT BUILT** |

The **critical remaining gap** is not subsystem-level incompleteness — it is that A/B (which ARE built) are not wired to the running chat endpoint. A partial MicroCompact (subsystem D), structured session notes (subsystem E), and task tracking (subsystem F) are the next build priorities.

---

## 0. Executive Summary

The project has **three structural disconnects** that must be resolved before any user-visible quality improvement will land:

1. **Harness-API Disconnect (Critical):** The sophisticated backend harness (PreTurnInjector, WikiEngine, 13-skill registry, guardrails, SandboxExecutor with DuckDB globals) is fully built but not wired to `chat_api.py`. The running chat endpoint uses a legacy 2-tool simplified version with a "financial analyst" prompt that says "call execute_python AT MOST ONCE."

2. **Frontend Routing Disconnect (High):** All 7 OS-platform section components are built (`sections/`), `IconRail.tsx` exists, but `App.tsx` still routes to `SessionLayout`. The new sections are unreachable from the UI.

3. **Long-Session Capability Gap (High):** Missing proactive compaction, persistent cross-session memory, in-session task tracking, and plan mode. The agent loses context gradually and starts cold every session.

Closing disconnect #1 alone would transform the agent from a toy chat interface into the full analytical platform it was designed to be.

---

## 1. True Current State (Reality Check)

### 1.1 Backend API vs Harness: What Actually Runs

| Component | Built? | Wired to chat_api.py? |
|---|---|---|
| `AgentLoop.run_stream()` (SSE generator) | ✅ | ✅ (via `_stream_agent_loop`) |
| `ToolDispatcher` | ✅ | ✅ (2 tools only) |
| `execute_python` tool | ✅ | ✅ |
| `write_working` tool | ✅ | ✅ (but writes are in-memory only — no filesystem persistence in this path) |
| `delegate_subagent` (A2A) | ✅ | ❌ NOT wired — a2a.py exists but not registered in chat_api.py dispatcher |
| `PreTurnInjector` | ✅ | ❌ NOT used — chat_api.py uses `_SYSTEM_PROMPT_BASE` local string |
| `WikiEngine` (working.md, findings) | ✅ | ❌ NOT wired from chat_api.py |
| `SkillRegistry` (13 skills) | ✅ | ❌ NOT wired from chat_api.py |
| `skill_tools.register_core_tools()` (15+ tools) | ✅ | ❌ NOT called from any API endpoint |
| `Guardrails` (pre_tool, post_tool, end_of_turn) | ✅ | ✅ (AgentLoop calls them) |
| `ContextManager` / `session_registry` | ✅ | ⚠️ Partially — chat_api.py imports session_registry but may not register layers |
| `ModelRouter` | ✅ | ❌ NOT used — model selected by request param |
| `TurnWrapUp` | ✅ | ❌ NOT called from chat_api.py |
| `SandboxExecutor` (real subprocess) | ✅ | ⚠️ Used via skill_tools but that path isn't wired |
| DuckDB globals bootstrap | ✅ (`sandbox_bootstrap.py`) | ⚠️ Partially — `build_duckdb_globals()` is imported but wiring unclear |

**What the running chat endpoint actually does:**
```
User sends message → chat_api.py →
  _stream_agent_loop() →
    System prompt = "_SYSTEM_PROMPT_BASE" ("financial analyst, AT MOST ONCE python call")
    Dispatcher with 2 tools: execute_python, write_working
    AgentLoop.run_stream() → SSE events → frontend
```

**What was designed to happen:**
```
User sends message → chat_api.py →
  PreTurnInjector.build() →
    System = prompts/data_scientist.md + wiki.working_digest() + skill_menu + gotchas
  register_core_tools(dispatcher, artifact_store, wiki, sandbox, session_id) →
    15+ tools registered (run_sandbox, save_artifact, load_skill, correlate, profile, ...)
  AgentLoop.run_stream() → SSE events → frontend
```

### 1.2 Frontend: What's Visible vs. What's Built

| Feature | Built? | Reachable from UI? |
|---|---|---|
| SessionLayout (3-panel: LeftPanel, ChatWindow, SessionRightPanel) | ✅ | ✅ (root route) |
| MonitorPage (`#/monitor/:id`) | ✅ | ✅ (hash route) |
| IconRail (48px rail with 7 section icons) | ✅ | ❌ NOT wired in App.tsx |
| ChatSection.tsx | ✅ | ❌ |
| AgentsSection.tsx (card grid with filter tabs) | ✅ | ❌ |
| SkillsSection.tsx | ✅ | ❌ |
| PromptsSection.tsx | ✅ | ❌ |
| ContextSection.tsx (stacked bar + layer breakdown + compaction history) | ✅ | ❌ |
| DevtoolsSection.tsx | ✅ | ❌ |
| SettingsSection.tsx | ✅ | ❌ |
| TerminalPanel.tsx | ✅ | ⚠️ SessionRightPanel may or may not use it |
| ToolCallsPanel.tsx | ✅ | ⚠️ Both exist; which is active unclear |
| ArtifactsPanel.tsx | ✅ | ⚠️ |
| ScratchpadPanel.tsx | ✅ | ⚠️ |
| ContextBar.tsx | ✅ | ❌ (only visible via ContextSection) |

### 1.3 Backend API Endpoints: What Exists

All APIs registered in `main.py`:

| Endpoint group | Registered? | Notes |
|---|---|---|
| `GET /api/health` | ✅ | |
| `POST /api/chat`, `POST /api/chat/stream` | ✅ | Uses simplified 2-tool path |
| `GET /api/conversations`, `POST /api/conversations` | ✅ | |
| `GET /api/context`, `GET /api/context/{session_id}`, `GET /api/context/{session_id}/history` | ✅ | Per-session endpoints exist |
| `GET /api/skills/manifest`, `GET /api/skills/{name}/detail` | ✅ | Skills API complete |
| `GET /api/prompts` | ✅ | prompts_api.py registered |
| `GET /api/trace/traces`, `GET /api/trace/traces/{session_id}` | ✅ | |
| `POST /api/datasets/upload` | ✅ | datasets_api.py registered |
| `GET /api/models` | ✅ | |
| `GET /api/settings` | ✅ | |
| `GET /api/data/status` | ✅ | |

---

## 2. V2 Phase Status (Updated Assessment)

| Phase | Planned | Actual Status |
|---|---|---|
| P7 — OS Platform Layout | Build IconRail + SectionRouter, wire App.tsx | **PARTIAL**: Components built, App.tsx NOT updated |
| P8 — Skills Explorer | SkillsSection with source viewer | **PARTIAL**: SkillsSection.tsx exists, backend `/api/skills/{name}/detail` exists |
| P9 — Monitoring Dashboard | AgentsSection with live card grid | **MOSTLY DONE**: AgentsSection.tsx looks complete |
| P10 — Prompts Registry | PromptsSection with token metadata | **PARTIAL**: PromptsSection.tsx exists, prompts_api.py exists |
| P11 — Context Inspector | ContextSection with stacked bar + compaction diff | **MOSTLY DONE**: ContextSection.tsx complete, context_api.py has all endpoints |
| P12 — Terminal Progress Panel | TerminalPanel replaces ToolCallsPanel | **PARTIAL**: TerminalPanel.tsx exists alongside ToolCallsPanel.tsx — not cleanly swapped |
| P13 — Chart/Artifact Rendering | VegaChart.tsx, DataTable.tsx | **UNKNOWN**: ArtifactsPanel.tsx exists but VegaChart wiring unclear |
| P14 — Gap Analysis Document | Write docs/gap-analysis.md | **DONE** (original, now superseded by this v2) |

**Blocker shared by ALL v2 phases:** None of the new sections are reachable because App.tsx hasn't been updated. Even if every section is perfect, users see the old SessionLayout.

---

## 3. Gaps vs. claude-code-main (Deep Analysis)

### 3.1 Agent Loop & Harness

**cc-main's agent loop** (`src/tools/AgentTool/runAgent.ts`) is a fully-featured multi-turn execution engine with:
- Subagent spawning with isolated context (readFileState, abortController)
- Frontmatter-based MCP server integration per agent
- Hook execution (preToolUse, postToolUse, Stop)
- Task tracking across turns
- Multiple compaction strategies
- Content replacement state for large tool results
- Session transcript recording per agent
- DreamTask background memory consolidation

**Agent's loop.py** has:
- Basic multi-turn execution ✅
- Guardrails (pre/post tool) ✅
- SSE streaming ✅
- A2A delegation (but not wired to chat_api.py) ✅
- **Missing**: Hooks, task tracking, proactive compaction, content trimming

### 3.2 Context Compaction (Critical Gap for Long Sessions)

CC-main has **four distinct compaction strategies**:

| Strategy | CC-main file | What it does | Agent equivalent |
|---|---|---|---|
| Full compact | `compact.ts` | Sends conversation to model, gets summary, replaces history | ❌ NONE |
| MicroCompact | `microCompact.ts` | Clears tool result blocks from message history beyond a window, keeps last N | ❌ NONE |
| API Micro compact | `apiMicrocompact.ts` | Uses Anthropic API `context_management.edits` (clear_tool_uses_20250919) | ❌ NONE |
| Session memory compact | `sessionMemoryCompact.ts` | Compacts session memory before injection to stay under token limit | ❌ NONE |

Agent's `ContextManager`:
- ✅ Tracks layer token counts
- ✅ Detects when `compaction_needed` (utilization ≥ threshold)
- ✅ Records compaction history (but only if compaction is called externally)
- ❌ Never triggers compaction — `compaction_needed` property is never read by the loop
- ❌ No compaction action is implemented

**Impact on long sessions:** The agent's context fills up with tool results from previous steps (DuckDB query outputs, Python stdout) with no cleanup. After 10-15 turns in a complex session, the model is spending context on stale intermediate results instead of the current analysis.

### 3.3 Background Memory Consolidation (DreamTask)

CC-main's DreamTask (`src/services/autoDream/`):
- Fires as a background forked subagent
- Trigger: time since last consolidation ≥ 24h AND at least 5 sessions touched
- Phases: orient → gather → consolidate → prune
- Reads session transcripts, produces MEMORY.md entries
- UI surfacing: visible as "dream" pill in footer during consolidation

Agent: **Nothing equivalent.** The wiki engine can write findings to `wiki/findings/*.md` but:
- No automatic consolidation
- No background processing
- No cross-session recall mechanism

### 3.4 Session Memory (Cross-Session Continuity)

CC-main's SessionMemory (`src/services/SessionMemory/`):
- Template with 9 sections: Current State, Task specification, Files and Functions, Workflow, Errors & Corrections, Codebase Documentation, Learnings, Key results, Worklog
- Updated at session end by an LLM call (Edit tool calls in parallel)
- Character limit per section (~2000 chars) prevents unbounded growth
- Injected as system prompt context in next session

**Agent's equivalent** (wiki/working.md):
- ✅ Per-session scratchpad with `write_working` tool
- ✅ Injected into system prompt via `_operational_state()` in PreTurnInjector
- ✅ Limited to 200 lines (prevents bloat)
- ❌ NOT wired to chat_api.py (PreTurnInjector not called)
- ❌ No structured template (free-form markdown)
- ❌ No automatic session-end LLM consolidation
- ❌ Not cross-session (working.md is in the wiki, not the session state)

**The working.md system IS the right architecture** — it just needs to be wired and have a structured template modeled after CC-main's SessionMemory.

### 3.5 Task Management

CC-main tools: `TaskCreate`, `TaskUpdate`, `TaskStop`, `TaskList`, `TaskGet`.

These allow the agent to:
- Break complex work into explicit tasks with names and statuses
- Track which tasks are complete vs in-progress across multiple turns
- Parallelize independent tasks across subagents

Agent: **None.** Long multi-step analyses (profile → test hypothesis → model → report) have no formal task structure. The `write_working` tool writes a TODO section in working.md, but there's no machine-readable task state.

### 3.6 Plan Mode

CC-main: `EnterPlanMode` / `ExitPlanMode` tools.

When in plan mode:
- The agent can only think, not execute destructive operations
- User reviews the plan before execution begins
- Critical for complex, irreversible operations

Agent: **None.** The data scientist system prompt encourages PLAN-first behavior but there's no enforced planning gate.

### 3.7 Hook System

CC-main settings.json hooks:
```json
{
  "hooks": {
    "PreToolUse": [{ "matcher": "Write|Edit", "command": "...", "description": "..." }],
    "PostToolUse": [{ "matcher": "Write|Edit", "command": "pnpm prettier --write \"$FILE_PATH\"" }],
    "Stop": [{ "command": "pnpm build" }]
  }
}
```

Agent: **None.** Guardrails exist but are internal code, not user-configurable shell commands.

### 3.8 Skill Loading (Full SKILL.md Access)

CC-main SkillTool: The agent calls `skill("skill-name")` to load the full SKILL.md content of a skill (including detailed instructions, examples, usage notes) into its context at the moment it needs to use it.

Agent:
- Descriptions injected always via PreTurnInjector (brief menu entry per skill)
- `load_skill_body` handler exists in skill_tools.py — but not wired to chat_api.py
- The agent cannot request the full SKILL.md instructions at runtime
- Result: agent only sees skill descriptions, never the detailed usage instructions

This is a significant capability gap: the agent knows a skill exists but can't get the "how to use it" documentation.

---

## 4. Gaps vs. deer-flow

### 4.1 Persistent Facts / User Memory

Deer-flow has a typed memory system with CRUD API:
```json
{
  "user": {
    "workContext": { "summary": "...", "updatedAt": "..." },
    "personalContext": { "summary": "...", "updatedAt": "..." },
    "topOfMind": { "summary": "...", "updatedAt": "..." }
  },
  "history": { "recentMonths": ..., "earlierContext": ..., "longTermBackground": ... },
  "facts": [{ "id": "fact_abc", "content": "...", "category": "preference", "confidence": 0.9 }]
}
```

These are injected into the agent's context automatically and updated after each conversation.

Agent: wiki/findings/*.md stores promoted findings per-project. The PreTurnInjector injects the wiki index. But:
- No structured user preferences / context section
- No confidence scores on findings
- No automatic memory update after each conversation

### 4.2 Checkpointing / Resumable Sessions

Deer-flow uses LangGraph checkpointing to persist full agent state (message history, graph state) to a database. Sessions can be resumed exactly where they left off.

Agent: **No checkpointing.** Each `POST /api/chat/stream` starts a fresh agent run with no memory of prior tool calls. The conversation history is stored (conversations_api.py) and the working.md is injected, but the full tool-call history is not recovered.

---

## 5. Gaps vs. Analytical-chatbot

### 5.1 Chart Rendering (In-Artifact-Panel)

Analytical-chatbot has `VegaChart.tsx` and `MermaidDiagram.tsx` that render charts inline in the ArtifactsPanel.

Agent: ArtifactsPanel.tsx exists but chart rendering wiring (vega-embed) is uncertain. The backend correctly stores artifact specs but frontend rendering may not be complete.

### 5.2 Terminal Progress Panel Quality

Analytical-chatbot's ProgressPanel:
- Rotating fun verbs per tool type (20+ verb sets)
- Per-tool icon mapping
- Live timer (100ms tick)
- Elapsed badge (ms/s/m format on completion)
- AnimatePresence for entry animations
- Terminal standby messages when idle
- Python code block collapsible previews

Agent's TerminalPanel.tsx exists but its quality vs Analytical-chatbot is unknown. The tool verb maps may not cover all agent tools.

---

## 6. Priority Gap Ranking (for Long-Session Capability)

### Tier 1 — Critical Path (Nothing works properly without these)

**P15: Wire the Full Harness to chat_api.py**  
*Impact:* Transforms the agent from a toy to a real analytical platform. All 13 skills, the data scientist prompt, DuckDB globals, wiki injection, and 15+ tools become active.  
*Effort:* Medium — all components exist, need to replace the simplified local functions in chat_api.py with the real harness.

**P16: Connect OS Platform Routing in App.tsx**  
*Impact:* All v2 section work (skills explorer, context inspector, agents, prompts) becomes reachable. Currently unreachable.  
*Effort:* Small — IconRail.tsx exists, SectionRouter pattern is clear. Update App.tsx root render.

### Tier 2 — Long-Session Capability (Directly addresses "without loss track")

**P17: Proactive Compaction in the Loop**  
*Impact:* Prevents context overflow in long sessions. Without this, complex multi-step analyses fail when tool results accumulate.  
*Effort:* Medium — implement MicroCompact strategy (drop tool result payloads beyond a window) in loop.py.

**P18: Structured Session Memory (cross-session continuity)**  
*Impact:* Agent recalls prior session decisions, rejected hypotheses, dataset knowledge. No more cold starts.  
*Effort:* Medium — model after CC-main's SessionMemory template, write at TurnWrapUp, inject at PreTurnInjector startup.

**P19: In-Session Task Tracking**  
*Impact:* Long multi-step analyses stay organized. Agent and user can see what's done, what's pending.  
*Effort:* Medium — add task state to TurnState, expose via working.md TODO section (already exists), add `create_task`/`update_task` tools.

### Tier 3 — Quality & Capability Upgrades

**P20: Full SKILL.md Loading (load_skill tool)**  
*Impact:* Agent can read detailed skill instructions at runtime, not just the brief description.  
*Effort:* Small — `load_skill_body` handler already exists in skill_tools.py, just needs wiring.

**P21: Token Budget Awareness Injected to Agent**  
*Impact:* Agent knows when it's near the context limit and proactively compresses working memory.  
*Effort:* Small — add context utilization to system prompt injection, add `get_context_status` tool.

**P22: Plan Mode Gate**  
*Impact:* Complex analyses get a review checkpoint before any code runs.  
*Effort:* Medium — add plan_mode flag to TurnState, enforce in pre_tool guardrail.

**P23: Hook System (PreToolUse / PostToolUse / Stop)**  
*Impact:* Enables automation (auto-save outputs, custom validation).  
*Effort:* Medium — add hook registry to ToolDispatcher.

### Tier 4 — Long-Term (Not blocking current use cases)

**P24: Background Memory Consolidation (DreamTask pattern)**  
**P25: File System Tools (Read/Write/Glob)**  
**P26: Persistent Facts Memory (deer-flow pattern)**  
**P27: Session Checkpointing**

---

## 7. What claude-code-agent Does Better

### 7.1 Context Visibility (Unique, No Equivalent in References)
Once wired, the ContextManager gives real-time visibility into:
- Which layers consume what tokens (system prompt, skill injections, conversation, tool results)
- Compaction history with before/after token counts
- Information loss flagging (what was dropped)

CC-main's compaction is completely opaque (API-native). Deer-flow has no context tracking.

### 7.2 Eval Framework (5-Level, Judge, Rubric)
No reference has this. The eval framework enables systematic quality measurement of outputs.

### 7.3 Data Infrastructure (DuckDB + Artifact Store + Schema Awareness)
Per-session DuckDB, dataset registry, schema-aware skills, artifact distillation (summaries in context, not raw data). This is the right architecture for analytical workloads.

### 7.4 Skill Dependency Graph (manifest.py)
Machine-readable DAG between skills. Prevents silent failures when upstream primitives change. No reference has this.

### 7.5 SSE Streaming Design (8 Typed Events)
Complete transparency into agent execution. Every turn, every tool call, every artifact, every scratchpad update visible in real time.

---

## 8. Architecture Decision Records (New)

**ADR-001: Wire harness first, then add capabilities**  
Rationale: P15 (harness wiring) unlocks all 13 skills, the data scientist prompt, DuckDB globals, and wiki integration in a single PR. Every subsequent capability improvement (compaction, session memory, task tracking) builds on a correctly-wired harness. Starting anywhere else builds on a broken foundation.

**ADR-002: Adopt CC-main's SessionMemory template for working.md**  
Rationale: The agent already has a working.md persistence mechanism that works correctly. Instead of building a parallel system, add structure to working.md using CC-main's 9-section template. This avoids new infrastructure while delivering cross-session continuity.

**ADR-003: Implement MicroCompact (not full compact) first**  
Rationale: Full compaction (summarize → replace history) requires a separate LLM call per compaction event, which adds latency and cost. MicroCompact (drop tool results beyond a window) is free, fast, and sufficient for 80% of long-session cases. Add full compact as a fallback when MicroCompact alone isn't enough.

**ADR-004: Token budget awareness in system prompt**  
Rationale: The most effective compaction strategy is one the model participates in. If the system prompt tells the agent "context is 78% full, prefer brief tool outputs and compress COT," the model will help manage its own context pressure.
