# Findings — ml-intern vs claude-code-agent Gap Analysis (2026-04-22)

> Previous entries below were from the Shell Foundation task (now shipped).

## ml-intern Gap Analysis Key Discoveries

### ml-intern architecture
- **Queue-based loop**: `submission_queue → event_queue`, operations typed as `OpType` enum (USER_INPUT, COMPACT, UNDO, EXEC_APPROVAL, SHUTDOWN)
- **litellm** for universal LLM provider support
- **doom_loop.py**: hashes tool call signatures, detects identical consecutive (3+) and repeating sequences (A,B,A,B) — claude-code-agent has no equivalent
- **effort_probe.py**: fires a 1-token ping on model switch, walks down `max→xhigh→high→medium→low` cascade per provider, caches per model
- **research_tool.py**: isolated subagent context for literature research (170k/190k token budgets), separate from main context
- **papers_tool.py**: Semantic Scholar API + ArXiv HTML reading, citation graph traversal, section-by-section reading
- Max 300 iterations, auto-compact at 170k tokens
- Session upload to HF Dataset repos (with retry)
- HF Jobs tool: spin up GPU training on Inference Endpoints

### claude-code-agent architecture (confirmed)
- Custom `AgentLoop` class in `app/harness/loop.py` (not LangGraph despite CLAUDE.md diagram mentioning it)
- Multi-client: Anthropic, MLX, Ollama, OpenRouter, fallback
- Parallel tool dispatch (8 workers, whitelist-based)
- 2-stage compaction: MicroCompactor + SemanticCompactor
- Full guardrails: pre-tool, post-tool, end-of-turn, tiered (ALLOW/WARN/BLOCK)
- Full trace bus: events, recorder, timeline, judge replay
- A2A protocol for subagent delegation
- Hierarchical skills: statistical analysis, charting, SQL, data profiler, etc.
- Full eval framework: judge, rubric, runner, grader, analyzer
- Wiki engine + second brain knowledge management
- Artifact store with distillation; Hooks system

## Top Borrow Candidates (priority order)
1. **Doom loop detection** — cheap, high-value, addresses real failure mode
2. **Effort probe cascade** — needed for robust multi-model support
3. **Papers tool** (Semantic Scholar) — literature grounding for analytical tasks
4. **Research subagent pattern** — isolated context prevents pollution
5. **GitHub code search** — validates implementation exists before proposing

---

## DS-Agent Shell Foundation (previous entries)

### Existing codebase state (pre-step-1)

### Current cockpit shape
- `frontend/src/App.tsx` renders `IconRail + SectionContent`
- `SectionContent` switches on `activeSection`: chat → `<Cockpit/>`, others → their own section components
- `<Cockpit/>` renders `TopHUD + ChatMain + RightRail` (no thread list)
- `RightRail` delegates to `TraceRail` (default mode) or one of `GraphPanel|DigestPanel|IngestPanel` via `useRightRailStore`
- Section list today: chat, agents, skills, prompts, context, health, settings

### Current styling
- Tailwind (utility-first) with `darkMode: ["selector", ":root:not(.light)"]` — dark default
- `frontend/src/styles/globals.css` defines hex-based tokens (`--color-bg-primary: #09090b`, `--color-accent: #e0733a`, etc.)
- `frontend/tailwind.config.ts` extends theme with many color families (brand.50..950, surface.50..950, canvas/ink/brand-accent/edge/success/warning/error/info/code-surface) — all kept intact
- Per-component CSS files exist (cockpit.css, ingest.css, etc.)

### Current fonts
- Only JetBrains Mono 400 and 500 self-hosted at `frontend/public/fonts/`
- Sans defaults to `system-ui, -apple-system, sans-serif`
- No serif loaded

### Current keyboard shortcuts (in App.tsx)
- `mod+k` — command palette
- `mod+n` — new conversation
- `mod+b` — toggle sidebar
- `mod+,` — settings
- `mod+l` — focus chat input
- `mod+/` — help
- `mod+\` — cycle rail (will be removed)
- `mod+shift+[` / `mod+shift+]` — prev/next conversation
- `mod+shift+f` — global search
- `mod+1..9` — switch conversation slot

## Design handoff bundle

- `design_handoff_ds_agent/` at repo root (top-level, gitignored currently)
- Files: tokens.css, app.jsx, shell.jsx, chat.jsx, progress.jsx, panels.jsx, icons.jsx, DS-Agent.html, README.md
- README explicitly calls out: "Don't ship the inline-Babel HTML." (prototypes only)
- Fidelity: hifi, pixel-matching expected

### Handoff token structure
- oklch-based for both themes (hue/chroma consistent)
- Light default in `:root`, dark override via `html[data-theme="dark"]`
- Semantic class system: .surface, .surface-raised, .mono, .serif, .label, .label-cap, .kbd, .dot, .btn (+.btn-primary/.btn-ghost), .row-hover, .ants, .pulse, .pulse-ring, .caret, .draw-check, .scale-in, .fade-in, .slide-in-r, .shimmer, .stripe-ph, .focus-ring
- Density variants via `html[data-density="compact|cozy"]`
- 8 signature keyframes: march (1s linear), pulse (1.8s ease-in-out), pulseRing (1.8s ease-out), blink (1.1s step), spin (0.9s linear), drawCheck (420ms ease-out forwards), scaleIn (280ms spring both), fadeIn (280ms ease-out), slideInR (260ms ease-out), sheen (2.4s ease-in-out)
- Motion tokens: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)` and friends

### Handoff layout
- 4-pane: 52px rail · 200px thread list (resizable) · flex conversation · 320px dock (resizable)
- Narrow-viewport auto-collapse: <1100 hides threads, <900 hides dock
- ThreadList width and Dock width persisted to localStorage (`ds:threadW`, `ds:dockW`)
- Resizers: 4px hit zone, cursor change, drag persists

### Handoff typography
- Sans: Söhne (proprietary) → Inter fallback
- Serif: Tiempos (proprietary) → Charter / Iowan Old Style / Palatino fallback
- Mono: SF Mono → JetBrains Mono fallback
- Body 13.5px / 1.5 / -0.003em
- Font features: `cv11, ss01, ss03` (sans), `zero, ss01, cv01` (mono)

## User decisions (this brainstorm, 2026-04-18)

| # | Decision | Chosen |
|---|----------|--------|
| Q1 | Decomposition | (A) 5 sub-projects, step 1 = Tokens & Shell Foundation |
| Q2 | Scope of new shell | (A) App-wide — IconRail + optional ThreadList + Section content + optional Dock |
| Q3 | Summon modes | (A) Promote Graph/Digest/Ingest to full IconRail sections |
| Q4 | Styling strategy | (A) Full Tailwind-extend |
| Q5 | Theme strategy | (C) Light-default, dark available |
| Q6 | Typography | (B) Inter + JBM self-hosted, OS serif |
| Q7 | IconRail item set | (A) Keep our section names, match handoff visuals, add Graph/Digest/Ingest |

## Open questions deferred to later steps

- Step 2 — chat header toolbar specifics, how it interacts with session dropdown removal
- Step 3 — Dock Progress-tab spec (timeline with pulse-ring, draw-check, marching ants)
- Step 4 — ThreadList pinned/archive behaviors, Command Palette rewrite
- Step 5 — Tweaks panel scope (developer-only vs user-facing)
