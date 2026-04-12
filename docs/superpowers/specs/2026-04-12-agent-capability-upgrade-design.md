# Agent Capability Upgrade — Design Spec

**Date:** 2026-04-12
**Target project:** claude-code-agent
**Status:** draft, pending user review

## 1. Motivation & Goal

Upgrade the agent from "runs code and makes charts" to "works like a disciplined data scientist." The upgrade has five coupled pillars:

1. A catalog of Altair chart skills with a shared, multi-variant theme system (cross-artifact color consistency for charts, tables, dashboards, reports).
2. Statistical skills (correlation, comparison, time-series, distribution-fit) with enforced gotcha handling.
3. A data-profiling skill that runs before analysis and surfaces structured risks.
4. A data-scientist system prompt that makes the agent follow a scientific-method working loop with evidence discipline.
5. A harness layer (model routing, state injection, guardrails) that keeps local-model behavior honest while leaving large-model behavior unconstrained.

The target agent runs locally on Gemma 4 26B (MoE, 48GB MBP) primarily, with optional escalation to Claude Sonnet / Opus for evaluation gates. The design must work well for small local models while not handcuffing large cloud models.

## 2. Architecture Overview

```
User turn
    │
    ▼
┌─────────────────────────────────────────┐
│  PreTurnInjector                        │
│    - static system prompt               │
│    - operational state (wiki digests)   │
│    - skill menu (descriptions only)     │
│    - gotchas index                      │
│    - active profile summary             │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  ModelRouter (per-stage model choice)   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  AgentLoop (Claude Code-style)          │
│    model → tool call → observation      │
│    ↑____________________↓               │
│                                         │
│    + Guardrails (tiered by model):      │
│       pre_tool_gate                     │
│       post_tool                         │
│       end_of_turn                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  TurnWrapUp                             │
│    - promote stable Findings to wiki    │
│    - update working.md, append log.md   │
│    - emit events                        │
└─────────────────────────────────────────┘
```

Three principles:
- **Agent self-organizes from skill descriptions** (Claude-Code-style flexibility).
- **Code enforces discipline at three touch-points** (pre_tool, post_tool, end_of_turn).
- **Enforcement tier scales with model size**: strict for small local models, observatory for large cloud models.

## 3. Skill Catalog (13 skills, 3 levels)

### Level 1 — Primitives (always loaded)
| Skill | Purpose |
|---|---|
| `theme_config` | Unified color/typography/spacing tokens, variant switching |
| `altair_charts` | 20 pre-themed chart templates + composition primitives |
| `html_tables` | Themed HTML table renderer |
| `data_profiler` | Full dataset profile with structured risk output |
| `sql_builder` | DuckDB query helpers |

### Level 2 — Analytical (on-demand)
| Skill | Purpose |
|---|---|
| `correlation` | Multi-method correlation with CI, nonlinear detection, partial corr |
| `group_compare` | Effect-size-first comparison with method auto-selection |
| `time_series` | Stationarity, decomposition, anomaly, changepoint, lag-corr |
| `distribution_fit` | Best-fit distribution with GOF, tail detection, Q-Q |
| `stat_validate` | PASS/WARN/FAIL gate before promoting any Finding |

### Level 3 — Composition (on-demand)
| Skill | Purpose |
|---|---|
| `analysis_plan` | Scaffolds investigation steps given a question |
| `report_builder` | Composes research_memo / analysis_brief / full_report |
| `dashboard_builder` | Composes bento-grid dashboards (HTML + A2UI embed) |

### Skill file format (matches Claude Code)

```
backend/app/skills/<skill_name>/
├── SKILL.md           # frontmatter: name, description, level (+ body)
├── skill.yaml         # optional: dependencies, error_templates
├── <entry>.py         # main entrypoint
└── tests/
```

Frontmatter:
```yaml
---
name: correlation
description: <one-line menu description>
level: 2
---
```

Agent sees `name + description` in the skill menu, then loads full SKILL.md body via the `skill` tool when ready to use it. Same pattern as Claude Code's Skill tool.

## 4. Data Scientist System Prompt

Static file at `prompts/data_scientist.md`, ~1,100 tokens. Always injected.

### 4.1 Identity & working loop (7 steps)

1. **ORIENT** — Read working.md + index.md. Check DuckDB schema. Write TODO in scratchpad.
2. **PLAN** — State hypothesis. Commit to method. Record in scratchpad COT.
3. **VALIDATE** — Run `data_profiler` on unfamiliar data. Address blockers before proceeding.
4. **ANALYZE** — Write code in sandbox. One focused operation per block. Save artifact or print summary.
5. **SENSE-CHECK** — Run `stat_validate` on any inferential claim. Effect size > p-value. Investigate suspicious findings.
6. **DEEPEN** — Loop back to PLAN with the next question.
7. **RECORD** — Promote stable Findings to `wiki/findings/`. Update working.md + log.md.

### 4.2 Python sandbox discipline

Pre-injected globals: `df`, `np`, `pd`, `alt`, `duckdb`, `save_artifact`, and skill entrypoints (`profile`, `correlate`, `compare`, `characterize`, `fit`, `validate`, all chart templates).

Rules:
- One focused operation per code block.
- Every block either saves an artifact OR prints a short summary — never both silent.
- No reading data from outside the session's DuckDB unless explicitly asked.

### 4.3 Evidence discipline

Every quantitative claim cites an artifact ID. If no artifact exists for a claim, either create one or move the claim from Findings to COT.

### 4.4 Scratchpad (append-first)

Four sections: TODO / COT / Findings / Evidence.

Three rules:
1. Append; don't rewrite.
2. Every Finding gets `[F-<date>-<nnn>]` + artifact filename.
3. TODO items get checked in place (the only mutation allowed).

Optional (skip unless obviously useful): resummarize COT at phase boundaries, prune stale TODOs, promote stable Findings to wiki.

### 4.5 Wiki memory (Karpathy pattern)

Always in context: `working.md` (current focus, mutable, ≤200 lines), `index.md` (derived nav digest), `log.md` (append-only history).

On disk only: `findings/<id>.md` (one per stable Finding), `hypotheses/<id>.md` (open questions), `entities/<name>.md` (domain entities).

### 4.6 Skill menu (auto-injected)

Menu contains name + description only. Agent calls `skill(name=...)` to load the full body.

### 4.7 Statistical gotchas reference

14 gotchas in `knowledge/gotchas/`, one-line index injected into prompt. Full bodies loaded on-demand when `stat_validate` flags them.

### 4.8 Output style

Chart > table > narrative. Prefer a visual over a paragraph. Every chart uses the active theme.

### 4.9 Sub-agent delegation

Agent can delegate to a sub-agent via `delegate_subagent(task, tools_allowed)`. Sub-agent runs independently and returns a result. Used for bulk operations, heavy retrieval, or anything that would bloat the main context.

## 5. Model Routing Config

File: `config/models.yaml`

### 5.1 Modes

- `config` (default) — pin models explicitly per role.
- `auto` — heuristics decide per-request based on complexity.

### 5.2 Model profiles

```yaml
models:
  claude_opus:
    provider: anthropic
    model_id: claude-opus-4-6
    thinking_budget: 16000
  claude_sonnet:
    provider: anthropic
    model_id: claude-sonnet-4-6
    thinking_budget: 8000
  claude_haiku:
    provider: anthropic
    model_id: claude-haiku-4-5-20251001
  gemma_thinking:
    provider: ollama
    model_id: gemma4:26b
    host: http://localhost:11434
    keep_alive: 30m
    num_ctx: 32768
    options: {temperature: 0.3, num_predict: 4096}
  gemma_fast:
    provider: ollama
    model_id: bjoernb/gemma4-26b-fast
    num_ctx: 16384
  qwen_small:
    provider: ollama
    model_id: qwen2.5:7b-instruct
```

### 5.3 Role assignments (default `config` mode)

```yaml
roles:
  think:       gemma_thinking   # planning, hypothesis, deep analysis
  execute:     gemma_fast       # writing sandbox code, tool calls
  summarize:   gemma_fast       # turn wrap-up, findings promotion
  evaluate:    claude_sonnet    # sense-check, stat_validate gates
  skill_pick:  qwen_small       # picks subset when menu > N tokens
  embed:       local_bge
```

### 5.4 Warm-up

On boot, harness issues trivial gen to each model in `warmup:` list with `keep_alive=30m`. Prevents 20-40s cold-start on first real request.

### 5.5 Guardrail tiers

```yaml
guardrails:
  mode: per_tier
  retry_on_gate_block: null     # or e.g. claude_sonnet
```

Per-tier behavior:
- **strict** (gemma_*, qwen_*) — blocks on FAIL, warns on WARN.
- **advisory** (claude_haiku) — allows with warning.
- **observatory** (claude_sonnet, claude_opus) — telemetry only, never blocks.

Data-integrity hooks (artifact capture, output trim, event emission) always run regardless of tier — those are plumbing, not discipline.

Explicit per-call override allowed: `{"guardrail_override": "<reason>"}` — logged and audited.

## 6. Unified Theme System

5 variants, shared token names, GIR-inspired institutional aesthetic.

### 6.1 Variants

| Variant | Use |
|---|---|
| `light` | Default interactive analysis |
| `dark` | Dark-mode interactive |
| `editorial` | GIR-style research reports (warm cream surface) |
| `presentation` | Slide decks (higher contrast, bigger type) |
| `print` | Grayscale-safe PDF exports |

### 6.2 Series blues (named by role, 8 shades per variant)

```
series.actual      deepest navy  — "this is what happened" (anchor)
series.primary     oxford navy   — main series
series.secondary   royal navy    — second series
series.reference   steel blue    — benchmark / historical avg
series.projection  muted blue    — modeled projection
series.forecast    light blue    — forecast / "what might happen"
series.scenario    powder blue   — alternate scenario / shaded band
series.ghost       faintest blue — prior-period shadow
```

Stroke convention: actual solid 2.5px, reference dotted 1.5px, forecast dashed 1.5px. Skills pick roles; theme resolves shade + stroke.

### 6.3 Semantic roles

`primary`, `positive` (sage), `negative` (burgundy), `warning` (ochre), `info`, `neutral`, `highlight` (brass).

### 6.4 Categorical palette

18-color, blue-heavy, colorblind-safe (tested on deuteranopia/protanopia). Print variant stepped by luminance for grayscale fallback.

### 6.5 Typography

- Sans: Inter
- Mono: JetBrains Mono
- Serif: Source Serif Pro (editorial + print only)

Size scale: xs/sm/base/md/lg/xl/title. Weight scale: regular/medium/semibold/bold.

### 6.6 Per-variant overrides

Editorial: serif headings, cream surfaces, wider default charts. Presentation: larger base size (18px), 900×540 default chart, bolder categorical.

### 6.7 Files

```
config/themes/
├── tokens.yaml           # single source of truth (all variants)
├── altair_theme.py       # registers Altair theme
├── table_css.py          # HTML table <style> block
├── dashboard.css         # CSS variables (auto-generated)
└── theme_switcher.py     # picks variant from output context
```

## 7. Altair Chart Template Library

### 7.1 Four-layer doctrine

```
Layer 4: Templates      ← agent picks these first
Layer 3: Composed       ← facets, layers, concat (when template near-misses)
Layer 2: Themed         ← raw Altair + theme applied
Layer 1: Raw Altair     ← escape hatch
```

### 7.2 20 templates

**Comparison:** `bar`, `grouped_bar`, `stacked_bar`, `bar_with_reference`, `lollipop`, `dumbbell`

**Time Series:** `actual_vs_forecast` (flagship), `multi_line`, `area_cumulative`, `range_band`, `small_multiples`

**Distribution:** `histogram`, `kde`, `boxplot`, `violin`, `ecdf`

**Relationship:** `scatter_trend`, `correlation_heatmap`

**Flow / Change:** `slope`, `waterfall`

Exotic charts (Sankey, network, geo) not covered; fall through to raw HTML artifacts.

### 7.3 Template contract

- Takes DataFrame + field mappings + optional title/subtitle/annotations.
- Returns `alt.Chart` fully themed.
- No color/stroke arguments — theme resolves these.
- Errors name missing fields and list expected shape.
- Every template is 30-80 lines; small models can read one if needed.

### 7.4 Conventions (enforced by templates)

- Actuals: solid 2.5px, darkest blue.
- Forecasts: dashed 1.5px, lighter blue.
- References: dotted 1.5px, steel blue.
- Scenario bands: filled area at opacity 0.35.
- Titles left-anchored (GIR).
- Diverging scales use the diverging palette, not rainbow.

### 7.5 Chart annotations are a separate skill

Narration / callouts are NOT auto-generated by templates. A sibling `chart_annotations` skill (future) handles that.

## 8. Data Profiler Skill

### 8.1 Entry point

```python
report = profile(df, name="customers_v1", key_candidates=["customer_id"])
# report.summary         — one-paragraph, model-readable
# report.risks           — severity-sorted DataRisk list
# report.sections        — full section payloads
# report.artifact_id     — profile-json
# report.report_artifact_id — profile-html (editorial theme)
```

### 8.2 Sections

Schema, missingness, duplicates, distributions, dates, outliers, keys, relationships. Each section has a DuckDB fast path for large datasets.

### 8.3 Risk taxonomy (21 kinds)

`missing_over_threshold`, `missing_co_occurrence`, `duplicate_rows`, `duplicate_key`, `constant_column`, `near_constant`, `high_cardinality_categorical`, `low_cardinality_numeric`, `mixed_types`, `date_gaps`, `date_non_monotonic`, `date_future`, `outliers_extreme`, `skew_heavy`, `suspicious_zeros`, `suspicious_placeholders`, `unit_inconsistency`, `suspected_foreign_key`, `collinear_pair`, `class_imbalance`, `timezone_naive`.

Severity levels: BLOCKER / HIGH / MEDIUM / LOW. Each risk has a `mitigation` field.

### 8.4 Artifact integration (aligned with analytical-chatbot)

- New ArtifactType `profile` (not piggybacked on `table`).
- Formats: `profile-json` (machine-readable), `profile-html` (human report).
- SQLite-backed store, `(session_id, artifact_id)` composite key, 8-char UUID.
- EventBus emits on save and update.
- Distillation: `profile_summary` carries the ~200-token digest that survives context compaction.

### 8.5 Inline-vs-disk split

- `content_size < 512KB` → inline in SQLite.
- `content_size >= 512KB` → bytes to `data/artifacts/<session>/<id>.<ext>`, path in SQLite.
- Threshold adjustable later.

### 8.6 VALIDATE-step policy

- First encounter with dataset → harness auto-invokes `data_profiler`, injects summary into context.
- Follow-up turns over same dataset → agent decides whether to re-profile.
- Skipping validation requires stated reason in COT ("reusing profile <id> from turn N").
- All `--skip-validate` decisions logged for review.

## 9. Statistical Skills

### 9.1 `correlation`

Methods: Pearson, Spearman, Kendall, distance correlation, partial correlation. Auto-selects based on data (linearity, monotonicity, ordinal vs continuous, n).

Returns coefficient + 95% bootstrap CI + p-value + method used + nonlinear_warning. Always bootstraps CI. Never silently drops NA.

### 9.2 `group_compare`

Methods: Student's t, Welch, Mann-Whitney, paired t, Wilcoxon, ANOVA, Kruskal-Wallis. Auto-selects from normality + variance equality + sample size + paired status.

**Effect size reported first, p-value second.** Cohen's d, Cliff's delta, eta². Always bootstraps effect-size CI.

### 9.3 `stat_validate` — the gate

Runs before any inferential Finding gets promoted. PASS/WARN/FAIL verdict.

Rules:
- Effect-size gate (FAIL if CI entirely within negligible)
- Sample-size gate (FAIL on n<10 per group)
- Multiple-comparisons correction (WARN if >5 tests, p<0.05, no correction)
- Assumption violations (passed through from test)
- Simpson's paradox segmentation check
- Confounder risk (WARN on causal-shaped claim without controls)
- Spurious correlation heuristics
- Look-ahead / leakage detection

Returns `gotcha_refs` pointing at `knowledge/gotchas/<name>.md` for remediation.

### 9.4 `time_series`

Characterize: stationarity (ADF + KPSS combined), trend, seasonality, autocorrelation, anomalies preview, default decomposition chart.

Decompose via STL. Anomalies via seasonal ESD (if seasonal) or robust z (else). Changepoints via PELT. Lag-correlation refuses non-stationary inputs without accept flag.

### 9.5 `distribution_fit`

Candidates auto-picked from data shape (unbounded symmetric / positive skewed / bounded / count / bimodal). Ranks by AIC with BIC cross-check. GOF via KS (Lilliefors-corrected) + Anderson-Darling. Always saves Q-Q + PDF overlay artifacts. Hill estimator for heavy-tail detection. Outliers defined as tail > p=0.001 under best fit.

### 9.6 Gotchas knowledge base

14 files in `knowledge/gotchas/`: base_rate_neglect, berksons_paradox, confounding, ecological_fallacy, immortal_time_bias, look_ahead_bias, multicollinearity, multiple_comparisons, non_stationarity, regression_to_mean, selection_bias, simpsons_paradox, spurious_correlation, survivorship_bias.

INDEX.md (one-liner per gotcha) injected into system prompt. Full bodies loaded on-demand.

## 10. Harness Layer

### 10.1 Component list

| Component | Responsibility |
|---|---|
| `PreTurnInjector` | Assembles system prompt from static + operational state + menu + profile |
| `ModelRouter` | Resolves role → ModelClient, runs warm-up |
| `AgentLoop` | Runs the model → tool → observation loop until `end_turn` |
| `ToolDispatcher` | Routes tool calls to skill invocations or builtins |
| `SandboxExecutor` | Runs Python with pre-injected globals |
| `PostProcessor` | Three-touch-point guardrails |
| `TurnWrapUp` | Promotes findings, updates wiki, emits events |

### 10.2 Guardrail touch-points

**`pre_tool_gate`** (before tool):
- Block `sandbox.run` if code references `df` with no dataset loaded.
- Block `promote_finding` if no `stat_validate` PASS exists in turn trace.
- Block `correlation.lag_correlate` on non-stationary inputs without accept flag.

**`post_tool`** (after tool):
- Record artifact IDs into turn evidence.
- Trim large stdout/stderr to artifact refs.
- Inject gotcha body text when `stat_validate` flagged one.
- Emit artifact event to EventBus.

**`end_of_turn`** (before wrap):
- Verify scratchpad structure (TODO/COT/Findings/Evidence sections).
- Reject turn if Findings exist without artifact citations.
- Warn if quantitative claim made without any artifact.

### 10.3 Stage-to-tool mapping

| Tool | Next-step stage |
|---|---|
| `sandbox.run` | `execute` |
| `stat_validate` | `evaluate` |
| `summarize_turn` | `summarize` |
| (default) | `think` |

### 10.4 Tool surface exposed to model

- `skill(name)` — loads SKILL.md body (analog to Claude Code's Skill tool).
- `sandbox.run(code)`
- `save_artifact`, `update_artifact`, `get_artifact`
- `write_working(content)`, `promote_finding(...)`
- `delegate_subagent(task, tools_allowed)`

### 10.5 Sandbox pre-injected globals

```python
df, np, pd, alt, duckdb, save_artifact,
profile, correlate, compare, characterize, fit, validate,
# all chart templates from skills.altair_charts
```

### 10.6 Wiki state files

- `working.md` — mutable, ≤200 lines, rewritten each turn.
- `index.md` — derived from wiki contents, rebuilt each turn.
- `log.md` — append-only.
- `findings/<id>.md` — one per stable Finding, never modified after write.
- `hypotheses/<id>.md`, `entities/<name>.md` — domain knowledge.

### 10.7 Token budget (typical)

```
Static system prompt        1,100
Operational state           1,600
Skill menu                    800
Gotchas index                 180
Active profile summary        200
Tool schemas                2,000
Conversation window       ~18,000
─────────────────────────────────
Total                     ~24,000 tokens

Gemma 4 26B num_ctx=32k    → 8k headroom per turn
Claude Sonnet 200k         → abundant
```

Compaction order when tight: conversation window → skill menu → gotchas index (last resort).

## 11. Report + Dashboard Builders

### 11.1 `report_builder`

Three templates:
- **research_memo** (GIR-style, default) — left-anchored serif title, 3 key points, one section per Finding with chart + evidence + caveats, methodology section, appendix.
- **analysis_brief** (1-pager) — single column, one chart, three bullets.
- **full_report** — TOC, intro, themed Finding groups, discussion, extended appendix.

Rules:
- Key Points = 3 (not 5, not 7).
- Every claim cites an artifact ID.
- Methodology is not optional.
- Caveats are first-class (no empty caveat sections).
- Default theme: editorial.
- No Findings with stat_validate FAIL allowed.

Renders: Markdown (primary), HTML (editorial-themed), PDF (via weasyprint).

### 11.2 `dashboard_builder`

Layouts: `bento` (default), `grid`, `single_column`. Responsive breakpoints 320/768/1024/1440.

KPI cards: `direction` flag flips semantic color (churn up ≠ revenue up). Optional sparkline. Delta always shown with comparison period.

Embed modes:
- `standalone_html` — self-contained, shareable, offline.
- `a2ui` — embedded in chat as first-class artifact.

Rules:
- Max 12 sections per dashboard.
- No placeholder / empty cards.
- Single theme per dashboard (all embedded charts re-render if theme mismatches).
- KPIs show delta or nothing.

## 12. Analytical-Chatbot Patterns Adopted

From `/Users/jay/Developer/Analytical-chatbot`:

- SQLite artifact store with composite `(session_id, artifact_id)` key.
- 8-char UUID slice for artifact IDs.
- Auto-slugged names with collision suffix.
- EventBus emission on save/update.
- In-place `update_artifact()` (preserves UI refinement UX).
- Distillation functions per type (preview field survives context compaction).
- `total_rows` / `displayed_rows` for truncation awareness.

Improvements over analytical-chatbot:
1. Add `profile` as first-class artifact type (not piggybacked on `table`).
2. Split artifact content to disk above 512KB threshold (SQLite stays lean).
3. Add `analysis`, `file` artifact types.
4. Profile-specific distillation (`profile_summary`) for context compaction.

## 13. Implementation Phases (high-level, detail in the implementation plan)

1. Theme system + Altair theme registration + table CSS renderer.
2. Skill registry + SKILL.md loader + `skill` tool.
3. Chart template library (20 templates).
4. Data profiler (schema + missingness + duplicates first; remaining sections follow).
5. Artifact store improvements (profile type, 512KB split, distillation).
6. Statistical skills (correlation, group_compare, stat_validate first; time_series, distribution_fit follow).
7. Gotchas knowledge base (14 files).
8. System prompt file + wiki scaffold (working/index/log).
9. Harness layer (injector, router, loop, dispatcher, sandbox, post-processor, wrap-up).
10. Model routing config + warm-up.
11. Report builder + dashboard builder.
12. Guardrail tiering.

Phases 1-3 unblock the rest; Phases 4-7 can run in parallel after.

## 14. Open Questions / Decisions Parked for Implementation

- Exact text of the 14 gotcha files (draft from existing references, polish per Finding we encounter).
- 512KB inline-vs-disk threshold — kept, revisit after first real usage.
- `report_builder` PDF engine choice (weasyprint vs wkhtmltopdf) — decide during Phase 11.
- `analysis_plan` skill — included in catalog, detail deferred to implementation.
- Whether to extract dashboard `a2ui` renderer as shared component or duplicate from analytical-chatbot — defer.

## 15. Success Criteria

- Agent runs the 7-step loop without prompting on a new dataset.
- `data_profiler` surfaces a BLOCKER before the agent can perform any bad-key join.
- `stat_validate` catches a Simpson's paradox case in adversarial testing.
- Theme swap (light → editorial) takes zero skill-code changes.
- Report render produces identical content across Markdown, HTML, and PDF except for format-appropriate presentation.
- Small-model run (Gemma 4 26B) completes a 5-finding analysis end-to-end with the same output discipline as a Claude Sonnet run.
- Guardrails never block a Sonnet run; always block a Gemma FAIL unless explicitly overridden.

## 16. Non-Goals

- Forecasting skill (use statsforecast / darts externally).
- Causal inference beyond partial correlation.
- Interactive filter UI for dashboards beyond what Altair natively supports.
- Real-time streaming dashboards.
- Multi-language beyond Python/SQL.
- Cross-session artifact sharing.

---

**Review notes**
- Terms: "agent" = the main working agent; "harness" = the code layer around it; "skill" = a module the agent can load and follow.
- File paths assume the project root at `/Users/jay/Developer/claude-code-agent/`.
- This design deliberately does not specify exact line counts or function signatures beyond what is needed for architectural clarity. The implementation plan (next step) will translate each section into sized, sequenced tasks.
