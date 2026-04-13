# Eval-Failure Response SOP — Design

**Date:** 2026-04-12
**Status:** Approved (brainstorm complete)
**Related:** `docs/superpowers/specs/2026-04-11-eval-framework-design.md`, `docs/superpowers/plans/2026-04-11-eval-framework.md`

---

## Problem

The eval framework (Levels 1–5, A/B/C grading) will tell us *that* the agent failed. It will not tell us *why*, *what to change*, or *whether a fix actually improves things without regressing other levels*. Without a structured response procedure, every failure becomes ad-hoc debugging — which means most failures get shallow fixes, root causes compound, and the agent drifts below the "good enough" bar (B on all levels).

This spec defines the **Eval-Failure Response SOP**: a manual-invocation procedure (`/sop <level>`) that triages a failing eval run to a root-cause bucket, proposes fixes from a cost-ordered ladder, logs the outcome, and feeds back into monitoring UI so developers can diagnose failure patterns visually.

## Goals

- Every failing eval below B has a deterministic path from "failure signal" → "root-cause bucket" → "fix candidate"
- No agent-side change is made before pre-flight rules out eval-bias / data-quality / determinism failures
- Every SOP session produces a structured log entry so future sessions get smarter (ladders → decision trees)
- Failure patterns are visible in DevTools so humans can diagnose without reading raw traces
- Buckets graduate from human-approved to autonomous only when iteration data proves readiness

## Non-Goals

- Fully autonomous SOP from day one (v1 is Claude-proposes / human-approves)
- A diagnostic harness that mutates the agent live to find root cause (Scope C — separate brainstorm after A+B ship)
- Automatic PR creation (SOP produces proposals; human applies them in v1)

---

## Scope

- **(A) Playbook** — `/sop` command, ladders per bucket, iteration log, FailureReport contract
- **(B) Monitoring UI** — 4 DevTools views for diagnosis
- **(C) Diagnostic harness** — deferred

---

## Architecture

### Two-stage triage

```
┌─ Pre-flight (always runs, cheap) ──────────────────────┐
│  7. Evaluation bias  →  8. Data quality  →  9. Determinism │
│  If any fires: fix the eval apparatus, not the agent.  │
└────────────────────────────────────────────────────────┘
                            ↓ agent-side only
┌─ Main triage (stops at first actionable bucket) ───────┐
│  cost-ordered:                                         │
│  1 Context → 2 Prompt → 3 Capability                   │
│        → 4 Routing → 5 Architecture → 6 Harness        │
└────────────────────────────────────────────────────────┘
```

Each bucket owns a **ladder** of fix candidates ordered cheapest-first. Ladders start as flat lists; they evolve toward decision trees as the iteration log accumulates evidence for which fixes work for which failure signatures.

### Bucket taxonomy (9 total)

#### Pre-flight buckets

| # | Bucket | Coverage | Characteristic symptoms |
|---|---|---|---|
| 7 | **Evaluation bias** | Judge miscalibrated, rubric ambiguous, fixture stale | Same trace grades differently across N judge runs; justification contradicts score |
| 8 | **Data quality** | Seed data changed, schema mismatch, planted-anomaly count drift | Deterministic tests flake; Level 3 recall collapses with no agent change |
| 9 | **Determinism** | Agent gives different output same input, temperature leakage, non-deterministic tool ordering | Re-run of same eval produces different grade |

#### Main-triage buckets (cost-ordered)

| # | Bucket | Coverage | Characteristic symptoms |
|---|---|---|---|
| 1 | **Context** | Compaction loss, scratchpad misuse, stale layers | Level 5 state drift; tokens balloon mid-session; scratchpad never written |
| 2 | **Prompt** | System-prompt contradictions, missing guidance, misleading framing | Agent does opposite of instruction; conflicting directives in assembled prompt |
| 3 | **Capability** | Skill instructions unclear, missing Python helpers, skill too bloated | Skill invoked but produces wrong output; skill token cost dominates |
| 4 | **Routing** | Wrong model for the job | Haiku doing architecture; Opus doing mechanical |
| 5 | **Architecture** | Missing subagent, needs parallelism, handoff vs. single-loop wrong | Level 5 fails on multi-step coordination; single-loop runs out of attention |
| 6 | **Harness** | Middleware missing fallback, tool error bubbling wrong, retries absent | Tool error aborts session; no retry on transient failure |

### Ladder structure (YAML per bucket)

```yaml
# backend/app/sop/ladders/01-context.yaml
bucket: context
description: "Compaction loss, scratchpad misuse, stale layers"
triage_signals:
  - scratchpad_writes == 0 with tool_calls > 5
  - compaction_events >= 3 in single session
  - token_count > 2x last-passing baseline
ladder:
  - id: context-01
    name: "Lower compaction threshold"
    cost: trivial        # one config value
    files: [backend/app/context/manager.py]
    pattern: "COMPACTION_THRESHOLD = 0.80 → 0.70"
  - id: context-02
    name: "Force scratchpad write on every tool return"
    cost: small          # one code path
    files: [backend/app/context/manager.py]
  - id: context-03
    name: "Add L2_skill layer pruning before compaction"
    cost: medium
    files: [backend/app/context/manager.py, backend/app/context/compaction.py]
  - id: context-04
    name: "Replace flat context with hierarchical summarization"
    cost: large          # architectural
    files: [backend/app/context/**]
```

## Data contracts

### FailureReport (runner → SOP)

Written by eval runner on any failing run. Path: `backend/tests/evals/reports/<YYYY-MM-DD>-level<N>.yaml`.

```yaml
level: 3
overall_grade: C
dimensions:
  detection_recall: {score: B, weight: 0.30}
  false_positive_handling: {score: D, weight: 0.30}   # primary failure
  methodology: {score: B, weight: 0.20}
  final_report: {score: C, weight: 0.20}

signals:
  token_count: 18400
  duration_ms: 47200
  compaction_events: 3
  scratchpad_writes: 0
  tool_errors: 1
  retries: 0
  subagents_spawned: 0
  models_used: {haiku: 12, sonnet: 0}

judge_justifications:
  false_positive_handling: "Agent flagged A4 (bonus) as suspicious despite clear salary pattern..."

top_failure_signature: "flagged_legitimate_pattern_as_anomaly"
trace_id: eval-2026-04-12-lvl3-a8f2
trace_path: backend/tests/evals/traces/eval-2026-04-12-lvl3-a8f2.json

diff_vs_baseline:
  baseline_date: 2026-04-10
  baseline_grade: B
  scratchpad_writes: {before: 8, after: 0}             # red flag
  token_count: {before: 12800, after: 18400, delta_pct: +43.75}
  subagents_spawned: {before: 2, after: 0}
  models_used_delta: {sonnet: -3, haiku: +7}
```

### Baseline snapshot

Path: `backend/tests/evals/baselines/level<N>.yaml`. Updated automatically after any run that scores ≥ B on the target level with no regression on others. Contains the same `signals` shape plus `date` and `trace_id`.

### Iteration log entry

One YAML per SOP session. Path: `docs/superpowers/sop-log/<YYYY-MM-DD>-level<N>-<NNN>.yaml`.

```yaml
date: 2026-04-12
session_id: 2026-04-12-level3-001
level: 3
overall_grade_before: C

pre_flight:
  evaluation_bias: pass
  data_quality: pass
  determinism: pass

triage:
  bucket: context
  evidence:
    - "scratchpad_writes: 8 → 0 since last B"
    - "token_count: +44% vs baseline"
    - "compaction_events: 3 in one session"
  hypothesis: "Compaction threshold too aggressive; scratchpad never reached"

fix:
  ladder_id: context-01
  name: "Lower compaction threshold 0.80 → 0.70"
  files_changed: [backend/app/context/manager.py]
  model_used_for_fix: sonnet
  cost_bucket: trivial

outcome:
  grade_after: B
  regressions: none
  iterations: 1
  token_delta_on_eval: -2100
  cost_delta_usd: -0.04
  judge_justifications_after:
    false_positive_handling: "Agent now correctly dismisses A4 (bonus) as salary pattern..."
  success: true

trace_links:
  before: backend/tests/evals/traces/eval-2026-04-12-lvl3-a8f2.json
  after:  backend/tests/evals/traces/eval-2026-04-12-lvl3-b3d1.json
```

## Workflow

### Trigger
Manual invocation: `/sop <level>`. No auto-fire, no PR hooks, no scheduled runs in v1.

### Cadence
1. Read latest `FailureReport` for the target level
2. Run **pre-flight** in order (Eval bias → Data quality → Determinism)
   - If any fires: produce diagnosis for the eval apparatus, skip main triage
3. Run **main triage**: evaluate bucket triage_signals in cost order
4. **Stop at first bucket with actionable signal** — propose its top ladder rung
5. Human approves → apply → re-run eval → write iteration log

### Termination
One of:
- Target level ≥ B with no regression on other levels → success, update baseline
- 3 iterations without reaching B → escalate to human, write log with `outcome.success: false`

### Autonomy

v1 default: **Claude proposes, human approves** per fix.

Per-bucket graduation to autonomous requires all of:
1. ≥ 5 SOP sessions triaged to this bucket
2. ≥ 80% of those sessions improved score with no regression
3. Ladder has ≥ 3 distinct rungs that have fired
4. Human flip in `.superpowers/sop-autonomy.yaml`:

```yaml
# .superpowers/sop-autonomy.yaml
autonomous_buckets:
  - context        # graduated 2026-05-01
# all others remain proposed/approved
```

**Reversibility:** a single autonomous run that produces a regression auto-reverts the bucket to proposed-mode and writes a log entry with `outcome.auto_reverted: true`.

## Monitoring UI (Scope B)

Ship order (each view earns its keep on day one):

### 1. SOP Session Replay (ship first)
Lists all iteration log entries. Each entry links to:
- Before/after trace JSON (rendered as step-by-step timeline)
- Judge justifications (before vs. after diff)
- Files changed (diff view)
- Grade chart (before vs. after on all dimensions)

Zero backend agent work required — reads only iteration log + trace files.

### 2. Judge Variance Dashboard
Runs the same trace through the LLM judge N times (configurable, default 5). Shows per-dimension variance. If variance > threshold for any dimension, Pre-flight bucket 7 (Evaluation bias) fires automatically.

### 3. Prompt Assembly Inspector
Shows the final assembled prompt for any step in a trace, with file-source attribution per section (e.g., "lines 12–34: `backend/app/prompts/system.md`"). Highlights contradictions between sections (heuristic: sections with directly opposing directives).

### 4. Compaction & Scratchpad Timeline
Token-layer stack chart over conversation turns. Compaction events overlaid as vertical lines. Scratchpad R/W log below timeline. Hover reveals layer content at that turn.

**Deferred to v2:** skill invocation log, model routing heatmap, subagent spawn graph, harness event stream, seed fingerprint, re-run variance.

## File layout

```
docs/superpowers/specs/2026-04-12-eval-failure-sop-design.md        # this spec
docs/superpowers/sop-log/                                            # iteration log entries
.superpowers/sop-autonomy.yaml                                       # bucket autonomy config

backend/app/sop/
  __init__.py
  triage.py                           # reads FailureReport, picks bucket
  ladders/
    01-context.yaml
    02-prompt.yaml
    03-capability.yaml
    04-routing.yaml
    05-architecture.yaml
    06-harness.yaml
    07-evaluation-bias.yaml
    08-data-quality.yaml
    09-determinism.yaml
  preflight.py                         # runs buckets 7, 8, 9
  reporter.py                          # writes FailureReport from eval output
  baseline.py                          # reads/writes last-passing snapshots
  log.py                               # iteration log read/write

backend/tests/evals/reports/           # FailureReport YAML per run (git-ignored)
backend/tests/evals/baselines/         # last-passing snapshots (committed)
backend/tests/evals/traces/            # raw trace JSONs (git-ignored)

frontend/src/devtools/sop/
  SessionReplay.tsx
  JudgeVariance.tsx
  PromptInspector.tsx
  CompactionTimeline.tsx
  api.ts                               # /api/sop/* endpoints

backend/app/api/sop.py                 # REST endpoints for DevTools views
```

## Success criteria

- First real eval failure triaged to the correct bucket within 1 SOP session (measured by human post-hoc confirmation)
- After 10 SOP sessions, at least one bucket meets graduation criteria
- Monitoring UI makes a failed eval diagnosable without reading raw trace JSON
- FailureReport diff-vs-baseline surfaces the primary signal change in every logged session

## Open questions (non-blocking)

- How does the SOP handle level-crossing regressions? (e.g., fix lifts L3 from C→B but drops L5 from B→C). v1 answer: terminate with `outcome.success: false`, flag the regression, human decides.
- Should the SOP ever propose *reverting* a prior fix whose iteration log shows a later regression? Deferred to after first 10 sessions — need data to decide.
