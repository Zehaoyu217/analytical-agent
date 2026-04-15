# Implementation Plan v3: claude-code-agent — Harness Wiring + Long-Session Capability

**Date:** 2026-04-15  
**Status:** approved  
**Builds on:** docs/progressive_plan_v2.md (P7–P14)  
**Key analysis:** docs/gap-analysis-v2.md  

---

## Context

V2 phases (P7–P14) are partially complete. The blocking issue: all new section components are built but unreachable because `App.tsx` hasn't been updated. A deeper and more urgent issue was discovered: the sophisticated backend harness (PreTurnInjector, 13-skill registry, WikiEngine, DuckDB globals) is built but not wired to `chat_api.py`. The running chat endpoint uses a 2-tool legacy path.

V3 fixes both disconnects and adds long-session capability.

---

## V2 Completion Status (pre-v3 baseline)

| Phase | Deliverable | Status |
|---|---|---|
| P7 | OS platform icon rail + section router | **PARTIAL** — components built, App.tsx not updated |
| P8 | Skills Explorer section | **PARTIAL** — SkillsSection.tsx + backend endpoints exist |
| P9 | Monitoring Dashboard (agent cards) | **MOSTLY DONE** |
| P10 | Prompts Registry section | **PARTIAL** |
| P11 | Context Inspector section | **MOSTLY DONE** |
| P12 | Terminal Progress Panel | **PARTIAL** — TerminalPanel.tsx exists alongside ToolCallsPanel.tsx |
| P13 | Chart/Artifact rendering | **PARTIAL** — ArtifactsPanel.tsx exists; VegaChart wiring unclear |
| P14 | Gap analysis document | **DONE** (now v2 supersedes it) |

---

## V3 Phase Summary

| Phase | Deliverable | Priority | Effort |
|---|---|---|---|
| **P15** | Wire full harness to chat_api.py | CRITICAL | Medium |
| **P16** | Connect OS platform routing in App.tsx | HIGH | Small |
| **P17** | Proactive MicroCompact in agent loop | HIGH | Medium |
| **P18** | Structured session memory (cross-session) | HIGH | Medium |
| **P19** | In-session task tracking | MEDIUM | Medium |
| **P20** | Full SKILL.md loading (load_skill tool) | MEDIUM | Small |
| **P21** | Token budget awareness in system prompt | MEDIUM | Small |
| **P22** | Plan Mode gate | MEDIUM | Medium |

---

## Phase 15 — Wire the Full Harness to chat_api.py

**Priority:** CRITICAL  
**Unblocks:** Everything. All 13 skills, real system prompt, DuckDB globals, wiki injection.

### Problem

`chat_api.py` defines `_build_dispatcher()` locally with only 2 tools and uses `_SYSTEM_PROMPT_BASE` (a hardcoded "financial analyst" string with "AT MOST ONCE" rules). The real harness (PreTurnInjector, register_core_tools, WikiEngine, SkillRegistry) is built in separate modules but never called from the API.

### Target Architecture

```
POST /api/chat/stream  →  _stream_agent_loop()
  ↓
  wiki = WikiEngine(knowledge/wiki/)
  registry = SkillRegistry.discover()
  gotchas = GotchaIndex(knowledge/gotchas/)
  injector = PreTurnInjector(prompts/data_scientist.md, wiki, registry, gotchas)
  system = injector.build(InjectorInputs(active_profile_summary=...))
  ↓
  sandbox = SandboxExecutor()
  artifact_store = ArtifactStore(session_id)
  dispatcher = ToolDispatcher()
  register_core_tools(dispatcher, artifact_store, wiki, sandbox, session_id, registry)
  ↓
  context_mgr = session_registry.get_or_create(session_id)
  context_mgr.add_layer(L1_system, L2_skills, ...)
  ↓
  AgentLoop(dispatcher).run_stream(client, system, user_message, ...)
```

### Files to modify

**`backend/app/api/chat_api.py`:**
- Remove `_SYSTEM_PROMPT_BASE`, `_build_dispatcher()` local definitions
- Import and call `PreTurnInjector.build()` for system prompt
- Import and call `register_core_tools()` for dispatcher
- Wire `WikiEngine`, `SkillRegistry`, `GotchaIndex` from their modules
- Wire `session_registry.get_or_create(session_id)` and register context layers
- Wire `build_duckdb_globals(session_id, dataset_path)` when a dataset is active
- Wire `TurnWrapUp` call after `AgentLoop.run_stream()` completes

**`backend/app/harness/wrap_up.py`** (verify TurnWrapUp signature):
- Call after run_stream() to promote findings, update log.md, emit events

**`backend/app/api/chat_api.py`** — tool schema list:
- Pass correct `tools` tuple from `register_core_tools` to `AgentLoop`

### Success criteria

- `pnpm dev` + `make backend`: chat works end-to-end
- Agent uses data scientist prompt (not "financial analyst AT MOST ONCE")
- `load_skill` tool call returns SKILL.md content
- `run_sandbox` tool runs Python in subprocess with DuckDB globals
- `save_artifact` tool saves to ArtifactStore and returns artifact_id
- Working.md contents appear in system prompt on the second turn

---

## Phase 16 — Connect OS Platform Routing

**Priority:** HIGH  
**Unblocks:** All V2 sections (Context Inspector, Skills Explorer, Agents Dashboard, etc.)

### Problem

`App.tsx` renders `<SessionLayout />` as root (old 3-panel chat). `IconRail.tsx` and all 7 sections exist in the repo but are never rendered.

### Changes

**`frontend/src/App.tsx`:**

Replace current root render with:
```tsx
if (monitorMatch) return <MonitorPage ... />

return (
  <ThemeProvider ...>
    <div className="flex h-dvh overflow-hidden">
      <IconRail />          {/* 48px — already built */}
      <SectionContent />    {/* full remaining width */}
    </div>
    ...
  </ThemeProvider>
)
```

**`frontend/src/components/layout/SectionContent.tsx`** (new, or use SectionRouter if it exists):
```tsx
// Read activeSection from store, render the correct section
switch (activeSection) {
  case 'chat': return <ChatSection />
  case 'agents': return <AgentsSection />
  case 'skills': return <SkillsSection />
  case 'prompts': return <PromptsSection />
  case 'context': return <ContextSection />
  case 'devtools': return <DevtoolsSection />
  case 'settings': return <SettingsSection />
}
```

**`frontend/src/sections/ChatSection.tsx`** — should wrap `SessionLayout` content (LeftPanel + ChatWindow + SessionRightPanel). Verify it does.

**`frontend/src/lib/store.ts`** — ensure `activeSection` state exists.

### Success criteria

- App loads with icon rail visible
- Clicking each icon navigates to the correct section
- Chat section behaves identically to current app
- Context Inspector, Skills Explorer, and Agents sections load their data

---

## Phase 17 — Proactive MicroCompact in Agent Loop

**Priority:** HIGH (long-session capability)  
**Addresses:** Context overflow in complex multi-step sessions

### Strategy: Tool Result Trimming (MicroCompact)

Modeled after CC-main's `microCompact.ts`:

After each tool call, if `total_tokens > threshold`:
1. Scan `messages` list backward from most recent
2. Find `role=tool` messages with large content (> 2000 chars)
3. Replace their `content` with a trimmed summary: `"[tool result trimmed — {artifact_id} saved]"`
4. Keep the last N tool results intact (configurable window, default = last 3)
5. Record the compaction event in ContextManager

Additionally, inject context pressure signal into system prompt when utilization > 70%:
```
## Context Status
Utilization: 78% (156,000 / 200,000 tokens).
Keep tool outputs brief. Prefer artifact summaries over inline data.
Compress COT if reasoning blocks are long.
```

### Files to modify

**`backend/app/harness/loop.py`:**
- Add `_micro_compact(messages, context_mgr, keep_last=3)` function
- Call after each tool result appended, when `context_mgr.utilization > 0.70`

**`backend/app/harness/injector.py`:**
- Add `_context_pressure_section(context_mgr)` method
- Include in `build()` when utilization > 0.70

**`backend/app/context/manager.py`:**
- Add `compacted_tool_count` counter
- `record_micro_compact(removed_count, tokens_freed)` method

### Success criteria

- A 20-turn session with large SQL outputs does not hit max_tokens error
- Context Inspector shows compaction events from micro-compact
- Agent adapts behavior when context pressure warning is injected

---

## Phase 18 — Structured Session Memory

**Priority:** HIGH (cross-session continuity, "without loss track")  
**Models:** CC-main's SessionMemory 9-section template  

### Design

**Session notes file:** `knowledge/wiki/session_notes/YYYY-MM-DD-HH-MM.md`

Template (modeled after CC-main):
```markdown
# Session: YYYY-MM-DD HH:MM

## Current State
_What was actively being worked on? Pending tasks not yet completed._

## Task
_What did the user ask to analyze? Key questions stated._

## Dataset State
_What datasets are loaded? Column types, row counts, notable issues found._

## Hypotheses Tested
_What hypotheses were tested? Results: confirmed/rejected/inconclusive._

## Key Findings
_Stable findings (stat_validate PASS) with artifact IDs._

## Rejected Approaches
_What didn't work and why. Do not retry these._

## Analysis Plan (Remaining)
_TODO items not yet completed._

## Worklog
_Terse step-by-step log of what was done._
```

**Write mechanism:** `TurnWrapUp` writes this file at end of each session (when `stop_reason == "end_turn"` and session has ≥ 2 turns).

**Read mechanism:** `PreTurnInjector` reads the most recent session notes file and injects as a new section:
```python
def _session_memory_section(self) -> str:
    notes_dir = self._wiki.root / "session_notes"
    if not notes_dir.exists():
        return ""
    files = sorted(notes_dir.glob("*.md"), reverse=True)
    if not files:
        return ""
    # Inject the most recent session notes
    content = files[0].read_text()[:3000]  # cap at 3000 chars
    return f"\n\n## Prior Session Memory\n\n{content}"
```

### Files to modify/create

**`backend/app/harness/wrap_up.py`:**
- Add `write_session_notes(wiki, turn_state, session_id, stop_reason)` method
- Write the 8-section notes template filled from turn_state data

**`backend/app/harness/injector.py`:**
- Add `_session_memory_section()` method
- Include in `build()` after `_operational_state()`

**`backend/app/wiki/engine.py`:**
- Add `write_session_notes(content, dt=None)` method
- Add `latest_session_notes()` → reads most recent notes file

### Success criteria

- After a session with ≥ 2 turns, a file appears in `knowledge/wiki/session_notes/`
- On the next session, the prior notes appear in the system prompt under "Prior Session Memory"
- The agent references prior hypotheses without being explicitly told about them

---

## Phase 19 — In-Session Task Tracking

**Priority:** MEDIUM (complex task management)

### Design

Add lightweight task state to `TurnState`:
```python
@dataclass
class Task:
    id: str
    name: str
    status: Literal["pending", "in_progress", "done", "blocked"]
    notes: str = ""
```

**Tools:**
- `create_task(name, notes="")` → creates task, returns task_id
- `update_task(task_id, status, notes="")` → updates status
- `list_tasks()` → returns current task list

**Persistence:** Task list is serialized as a structured section in working.md:
```markdown
## TASKS
- [x] F0001 — Profile housing dataset (DONE)
- [>] F0002 — Test price ~ size correlation (IN_PROGRESS)
- [ ] F0003 — Segment by region (PENDING)
```

TurnWrapUp writes the task list to working.md at end of each turn.

### Files to modify

**`backend/app/harness/turn_state.py`:** Add `Task` dataclass, `tasks: list[Task]` field, task CRUD methods.

**`backend/app/harness/skill_tools.py`:** Register `create_task`, `update_task`, `list_tasks` handlers.

**`backend/app/harness/wrap_up.py`:** Serialize tasks to working.md TASKS section.

---

## Phase 20 — Full SKILL.md Loading

**Priority:** MEDIUM  
**Effort:** Small (handler already exists)

### Problem

The `load_skill_body` handler already exists in `skill_tools.py`:
```python
def _load_skill_body(args: dict[str, Any]) -> dict:
    name = args.get("name")
    body = registry.get_instructions(name)
    return {"name": name, "body": body}
```

It's just not registered as a tool and therefore the agent can't call it.

### Changes

**`backend/app/harness/skill_tools.py`:** Add to `register_core_tools()`:
```python
dispatcher.register("load_skill", _load_skill_body)
```

Add tool schema to the ToolSchema tuple passed to AgentLoop.

**`backend/app/skills/registry.py`:** Verify `get_instructions(name)` returns the full SKILL.md body text.

### Success criteria

- Agent can call `load_skill("correlation")` and receive the full SKILL.md instructions
- The PreTurnInjector continues to inject only the brief skill menu (descriptions)
- Agent uses `load_skill` when it needs detailed usage instructions before using a skill

---

## Phase 21 — Token Budget Awareness

**Priority:** MEDIUM  
**Effort:** Small

### Design

**System prompt injection** (already specified in P17, formalized here):
```python
def _context_pressure_section(self, context_mgr: ContextManager) -> str:
    utilization = context_mgr.utilization
    if utilization < 0.70:
        return ""
    level = "MODERATE" if utilization < 0.85 else "HIGH"
    pct = round(utilization * 100)
    return (
        f"\n\n## Context Status\n\n"
        f"Utilization: {level} ({pct}%). "
        f"Keep tool outputs brief. Prefer artifact references over inline data. "
        f"Summarize completed analysis threads in working.md before starting new ones."
    )
```

**New tool: `get_context_status`:**
```python
def _get_context_status(args: dict[str, Any]) -> dict:
    snap = context_mgr.snapshot()
    return {
        "total_tokens": snap["total_tokens"],
        "max_tokens": snap["max_tokens"],
        "utilization_pct": round(snap["utilization"] * 100),
        "layers": [(l["name"], l["tokens"]) for l in snap["layers"]],
    }
```

---

## Phase 22 — Plan Mode

**Priority:** MEDIUM  
**Models:** CC-main's EnterPlanMode / ExitPlanMode

### Design

Add `plan_mode: bool` to `TurnState`. When plan_mode is True, the pre_tool guardrail blocks `run_sandbox`, `save_artifact`, and `delegate_subagent`.

**Tools:**
- `enter_plan_mode()` → sets plan_mode=True, returns confirmation
- `exit_plan_mode()` → sets plan_mode=False, returns confirmation

**System prompt addition:** When plan_mode is True, inject:
```
## Plan Mode Active
You are in planning mode. Only think and use list_tasks, write_working, load_skill.
Do NOT call run_sandbox, save_artifact, or delegate_subagent until plan mode ends.
```

---

## Execution Order

```
P15  ─── CRITICAL: wire harness ──────────────── enables everything below
P16  ─── after P15: routing fix ──────────────── unblocks all V2 sections
P20  ─── after P15: tiny win ─────────────────── load_skill tool (1 line change)
P21  ─── after P15: tiny win ─────────────────── context pressure injection
P17  ─── after P15+P21: MicroCompact ─────────── long-session compaction
P18  ─── after P15+P16: session memory ───────── cross-session continuity
P19  ─── after P15+P18: task tracking ────────── complex task management
P22  ─── after P19: plan mode ────────────────── analysis planning gate
```

**Parallel opportunities:**
- P20 + P21 can run in parallel with P16 (independent — all P15 dependent but not each other)
- P17 + P18 can run in parallel (both modify different files after P15)
- P19 + P22 can run in parallel

---

## Backend Change Summary

| File | Change | Phase |
|---|---|---|
| `backend/app/api/chat_api.py` | Wire PreTurnInjector, register_core_tools, WikiEngine, SkillRegistry, TurnWrapUp | P15 |
| `backend/app/harness/loop.py` | Add `_micro_compact()`, call after each tool result when utilization > 70% | P17 |
| `backend/app/harness/injector.py` | Add `_context_pressure_section()`, `_session_memory_section()` | P17, P18, P21 |
| `backend/app/harness/wrap_up.py` | Add `write_session_notes()` | P18 |
| `backend/app/wiki/engine.py` | Add `write_session_notes()`, `latest_session_notes()` | P18 |
| `backend/app/harness/turn_state.py` | Add `Task` dataclass, tasks list, CRUD methods | P19 |
| `backend/app/harness/skill_tools.py` | Register `load_skill`, `create_task`, `update_task`, `list_tasks`, `get_context_status` | P19, P20, P21 |
| `backend/app/context/manager.py` | Add `record_micro_compact()`, `compacted_tool_count` | P17 |

---

## Frontend Change Summary

| File | Change | Phase |
|---|---|---|
| `frontend/src/App.tsx` | Replace `SessionLayout` root with `IconRail + SectionContent` | P16 |
| `frontend/src/components/layout/SectionContent.tsx` | New: section router component | P16 |
| `frontend/src/sections/ChatSection.tsx` | Verify wraps SessionLayout content | P16 |

---

## Definition of Done (V3)

- [ ] Chat endpoint uses real data scientist system prompt (not "financial analyst AT MOST ONCE")
- [ ] Agent can call `load_skill("correlation")` and receive full SKILL.md instructions
- [ ] Python code runs in SandboxExecutor subprocess with DuckDB globals (`df`, `duckdb`, skill entrypoints)
- [ ] Artifacts saved via `save_artifact` appear in ArtifactStore and Artifacts panel
- [ ] A 20-turn session does not hit context limit (micro-compact running)
- [ ] Second session references prior session's hypotheses and dataset state
- [ ] Long analysis (profile → test → report) tracks tasks in working.md
- [ ] App.tsx renders IconRail; clicking Context opens ContextSection, clicking Agents opens AgentsSection
- [ ] All previous tests pass (`pytest backend/`, `pnpm build`)
- [ ] docs/gap-analysis-v2.md and docs/progressive_plan_v3.md committed
