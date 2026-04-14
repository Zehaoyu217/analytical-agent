# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What This Is

Analytical Agent — a full-stack analytical platform for MLE, data scientists, and quants. AI-powered data analysis with transparent agent operations, a skills system for composable analytical capabilities, and a developer workbench for full observability.

## Project Structure

| Directory | What | Modify? |
|-----------|------|---------|
| `backend/` | Python/FastAPI backend (agent, skills, sandbox, API) | Yes |
| `frontend/` | React+Vite analytical UI + devtools | Yes |
| `mcp/` | MCP explorer server | Yes |
| `infra/` | Docker, Helm, Grafana, Ollama | Yes |
| `knowledge/` | Wiki, graphify graphs, ADRs | Yes |
| `docs/` | SOPs, guides, gotchas | Yes |
| `scripts/` | Dev tooling scripts | Yes |
| `reference/` | Original Claude Code CLI source (read-only) | **No** |

## Commands

```bash
# Development
make dev              # Start backend + frontend + Ollama
make backend          # Backend only (uvicorn :8000)
make frontend         # Frontend only (vite :5173)

# Quality
make lint             # Ruff (backend) + ESLint (frontend)
make typecheck        # Mypy (backend) + tsc (frontend)
make test             # All tests
make test-backend     # pytest
make test-frontend    # vitest

# Skills
make skill-check      # Dependency manifest check
make skill-eval       # Run all skill evals
make skill-new name=X # Scaffold new skill

# Knowledge
make wiki-lint        # Run wiki lint cycle
make graphify         # Regenerate graphify output
```

## Architecture

```
Frontend (React+Vite :5173)
    ↕ REST + SSE
Backend (FastAPI :8000)
    ├── Agent (LangGraph) → Tools → Sandbox (subprocess Python)
    ├── Skills (registry + packages, importable in sandbox)
    ├── Wiki Engine (Karpathy pattern, knowledge/wiki/)
    ├── Context Manager (layer tracking, compaction)
    └── Data (DuckDB, dataset registry)
```

## Conventions

- **Backend:** Python 3.12+, Ruff formatter, type hints everywhere, Pydantic for schemas
- **Frontend:** TypeScript strict, Vite, Zustand for state
- **Tests:** pytest (backend), vitest (frontend), 80% coverage target
- **Commits:** `<type>: <description>` (feat, fix, refactor, docs, test, chore)
- **Skills:** SKILL.md < 200 lines, Python packages unlimited, errors must be actionable
- **Changelog:** every main update lands an entry in `docs/log.md` under `[Unreleased]` — see that file's header for the policy and entry shape.

## Changelog Policy

`docs/log.md` is the single source of truth for notable changes. **You must update it** before marking a task complete whenever the change is one of:

- A `feat:` commit that touches user-visible behavior or adds a capability
- A breaking change to a public interface (skill signature, tool registration, API schema, config schema)
- A migration, rename, or removal that affects existing callers
- A security, correctness, or data-loss fix on a critical path

Pure refactors, test-only commits, and doc-only commits do not require an entry unless they change observable behavior.

## Current State

Read `knowledge/wiki/working.md` for what's in progress.

## Deeper Context

- Architecture decisions: `knowledge/adr/`
- Development setup: `docs/dev-setup.md`
- Testing guide: `docs/testing.md`
- Skill creation: `docs/skill-creation.md`
- Known gotchas: `docs/gotchas.md`
- Changelog: `docs/log.md`

## Design Context

### Users
Machine learning engineers, data scientists, and quantitative analysts — technical power users running experiments, debugging pipelines, and interrogating data. They work under pressure and expect tools that keep up. The interface should make them feel **in command**: information-rich, fast, and authoritative. No hand-holding. No noise.

### Brand Personality
**Precise. Uncompromising. Technical.**

The product is a precision instrument, not a consumer app. Personality lives in structure, density, and micro-detail — not decoration. A developer who opens this tool should feel the same way they feel opening Warp or Raycast: this was built for people like me.

### Aesthetic Direction
**Swiss / Terminal**

Tight grid, monospace everywhere it makes sense, data density as a virtue. References: Warp, Raycast, Linear, Ghostty. Anti-references: consumer ChatGPT/Claude.ai, default shadcn/Tailwind dashboards, Jupyter Notebook, anything playful or pastel.

- Typography does the heavy lifting. Caps + slashes + weights create hierarchy without decorative chrome.
- JetBrains Mono is not just for code blocks — it's the voice of the UI at the system level (labels, metadata, status, timestamps).
- Near-black backgrounds (`#09090b`, `#18181b`) with purple (`#8b5cf6`) as the only color that matters.
- Borders are subtle lines that separate information, not decorative frames.
- Dark mode only. Light mode exists in the codebase but is not a design priority.
- Motion is functional: instant feedback, not spectacle. No easing curves that feel "designed."

### Design Principles

1. **Density is a feature** — compact controls, tight line heights, information reachable without scrolling. Never pad for breathing room that a power user didn't ask for.

2. **Monospace as personality** — JetBrains Mono at the system level (labels, status lines, metadata, timestamps). Sans-serif for prose content only. The type choice signals what kind of tool this is.

3. **Structure through text** — visual hierarchy via caps, weight contrast, and measured spacing. Not through cards, shadows, gradients, or decorative backgrounds. A `TRACES` label in small caps at 10px carries more weight than a shadowed card.

4. **Every state is visible** — loading, streaming, error, success, latency — all surfaced legibly. No spinner-and-pray. Power users need to know what the system is doing at all times.

5. **Dark is not a mode — it's the product** — design for the dark theme as if the light theme doesn't exist. High contrast within the dark palette; the purple accent should feel intentional, not decorative.

> Full context in `.impeccable.md` at project root.
