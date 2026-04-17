---
title: Self-maintaining doc/code/graph integrity system
status: design-approved
created: 2026-04-16
last_revised: 2026-04-16
owner: jay
sub_specs:
  - 2026-04-16-integrity-plugin-a-design.md  # Plugin A (graph extension), gate α
---

# Self-maintaining doc/code/graph integrity system

> Mega-spec covering sub-projects A–F as a coordinated roadmap. Each plugin
> gets its own focused sub-spec when its phase begins. This document is the
> single source of truth for the umbrella; edit in place, bump `last_revised`.

## 1. Goal

Build a system that keeps `claude-code-agent`'s code, docs, configs, and
knowledge graph **mutually consistent over time** without per-change manual
audit. Drift becomes visible (PR reports), then fixable (auto-PRs for safe
classes), then prevented (hooks that warn at edit time).

The motivating finding from Phase 9.3: graphify's edge extraction is too sparse
(539 EXTRACTED use-edges across 2605 code nodes, ~0.21 density) to detect dead
code reliably. 63% of "orphans" were false positives — handlers bound by URL
routing, intra-file calls, JSX usage. Fixing graphify is therefore the load-
bearing first step; everything else depends on a graph that can be trusted.

## 2. Non-goals

- Replacing existing tools (`make lint`, `make typecheck`, `make test`,
  `make wiki-lint`, `make skill-check`) — the integrity engine *augments* them.
- Detecting semantic doc bugs ("this paragraph is wrong"). Only mechanical /
  structural drift is in scope.
- Becoming a general-purpose static analyzer. Use vulture, knip, ts-prune,
  ruff for the heavy lifting; integrity *orchestrates and aggregates*.
- Auto-editing code logic. Autofix is restricted to a strict whitelist of
  mechanical fixes (see plugin F).

## 3. Operating model (decisions locked from brainstorm)

| Decision | Choice | Implication |
|----------|--------|-------------|
| Timeline | Dependency-driven, no calendar | Gates between sub-projects, not dates |
| Enforcement mode | PR-gated | Hooks warn but don't block; autofix opens PRs |
| Observability surface | Frontend Health section + `/api/health` | New section in OS-platform icon rail |
| Build shape | Deep-first vertical slice | Ship A fully, then B, etc. — production-grade per piece |
| Architecture | Plugin pipeline | Single engine, six plugins, one stable interface |

## 4. Architecture

```
backend/app/integrity/
  engine.py            # IntegrityEngine: discover plugins, run, aggregate
  schema.py            # IntegrityReport, IntegrityIssue, Severity, Source
  registry.py          # plugin discovery + manifest
  storage.py           # write reports → integrity-out/{date}/report.json + .md
  api.py               # FastAPI router mounted at /api/health
  plugins/
    graph_extension/   # A — graphify FastAPI/intra-file/JSX extractors
    graph_lint/        # B — nightly diff, drift/dead-code/orphan signals
    doc_audit/         # C — CLAUDE.md indexing, cross-link, freshness
    config_registry/   # E — unified inventory of skills/scripts/configs
    hooks_check/       # D — verify hooks fire on expected events
    autofix/           # F — narrow remediation, opens PRs only
```

### 4.1 Plugin protocol

Single interface every plugin implements:

```python
class IntegrityPlugin(Protocol):
    name: str                                      # stable identifier
    version: str                                   # semver, bump on output change
    depends_on: list[str]                          # other plugin names
    paths: list[str]                               # globs that trigger incremental scan

    def scan(self, ctx: ScanContext) -> list[IntegrityIssue]: ...
    def can_fix(self, issue: IntegrityIssue) -> bool: ...
    def fix(self, issue: IntegrityIssue) -> FixProposal | None: ...
```

`ScanContext` carries: repo root, prior-report cache, other plugins' fresh
outputs (so e.g. `doc_audit` can read `graph_extension`'s graph), config knobs
from `config/integrity.yaml`.

### 4.2 Report schema

```python
class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"      # plugin failed to run
    CRITICAL = "critical"  # rare; reserved for safety-of-the-system signals

class IntegrityIssue(BaseModel):
    plugin: str
    rule: str                       # plugin-internal rule id (e.g. "doc.broken_link")
    severity: Severity
    location: str | None            # "path/to/file.py:42" or "docs/foo.md#bar"
    message: str                    # human-readable
    evidence: dict[str, Any]        # structured details for autofix to consume
    fix_class: str | None           # if non-null, autofix may consider it
    first_seen: str                 # ISO date — for freshness/aging
    last_seen: str

class IntegrityReport(BaseModel):
    run_id: str
    started_at: str
    finished_at: str
    plugin_status: dict[str, Literal["ok", "failed", "skipped"]]
    plugin_versions: dict[str, str]
    issues: list[IntegrityIssue]
    summary: dict[str, int]         # counts by plugin × severity
```

### 4.3 Storage layout

| Path | Tracked? | Purpose |
|------|----------|---------|
| `integrity-out/{ISO-date}/report.json` | gitignored | Full machine-readable report |
| `integrity-out/{ISO-date}/report.md` | gitignored | Full human-readable mirror |
| `integrity-out/latest -> {ISO-date}/` | gitignored symlink | Convenience |
| `docs/health/latest.md` | committed | Summary surfaced in PRs/git history |
| `docs/health/trend.md` | committed | 30-day rolling counts (per-plugin × severity) |
| `config/integrity.yaml` | committed | Engine config: enabled plugins, thresholds, autofix toggles |
| `config/manifest.yaml` | committed | Output of plugin E — unified project inventory |

`docs/health/latest.md` is committed deliberately so drift is visible in
`git log` and PR reviews without standing up extra infrastructure.

### 4.4 API surface (`backend/app/integrity/api.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Latest `IntegrityReport` (cached, fast) |
| GET | `/api/health/history?days=N` | Run summaries across N days |
| POST | `/api/health/run` | Trigger full scan (auth-gated; idempotent if running) |
| POST | `/api/health/run?plugin=<name>` | Trigger single-plugin scan |
| GET | `/api/health/plugin/<name>` | Latest output for one plugin (drill-down) |
| POST | `/api/health/issue/<id>/dismiss` | Mark known-acceptable; persisted to `config/integrity.yaml` |

### 4.5 Frontend Health section

New entry in the OS-platform icon rail (next to Skills, Monitoring, Prompts,
Context, Terminal). Components:

- **Header**: last-run timestamp, total counts by severity, manual "Run scan"
  button (POST `/api/health/run`).
- **Per-plugin cards** (six): status badge (ok/failed/stale), issue count by
  severity, sparkline of last 14 nightly counts, drill-down button.
- **Issue table** (filterable by plugin, severity, fix_class): location,
  message, age, "dismiss" / "open PR" actions.
- **Trend view**: same data as `docs/health/trend.md` but live-rendered.

The Health section reuses existing patterns from Skills Explorer and
Monitoring Dashboard — no new design system work.

## 5. The six plugins

### 5.1 A · `graph_extension` *(deep-first slice)*

**Problem solved.** graphify currently misses three edge classes; downstream
signals depend on a graph that captures them.

**Extractors** (run after stock graphify completes; post-process its output):

1. **FastAPI extractor** — Walk `@router.{get,post,put,delete,patch,websocket}(path, ...)`
   decorators in `backend/app/api/**/*.py` and `backend/app/harness/**/*.py`.
   Emit:
   - One node per route: `route::<METHOD>::<path>` with attributes `method`,
     `path`, `handler_id`, `module`.
   - Edge `route → handler` (relation: `routes_to`, confidence: `EXTRACTED`).
   - Edge `app → route_inventory` summary node.
   Includes WebSocket and SSE handlers (`@app.websocket`, `EventSourceResponse`
   return-type detection).

2. **Intra-file call extractor** — Re-walk each module's AST after graphify
   semantic extraction; emit same-file `calls` edges that graphify currently
   drops. Specifically: any `Name` or `Attribute` in a `Call` position whose
   resolved target is defined in the *same file* gets a `calls` edge with
   `confidence: EXTRACTED`. Avoids re-extracting cross-file edges (graphify
   already has those).

3. **JSX extractor** — Parse `.tsx`/`.jsx` via `@babel/parser` (Node helper).
   For every `JSXOpeningElement` with a name matching an imported identifier,
   emit a `uses` edge from the containing component to the imported
   component's symbol. Confidence: `EXTRACTED`.

**Output.** Separate `graphify/graph.augmented.json` (sibling to stock
`graphify/graph.json`) with `extension: "cca-v1"` provenance tag on each new
node/edge. Original graphify output untouched. Consumers merge with read-
precedence. See sub-spec `2026-04-16-integrity-plugin-a-design.md`.

**Acceptance gate (deep-first).** False-positive orphan rate on the 100-symbol
sample (same script as Phase 9.3's `/tmp/verify_orphans.py`, kept as
`scripts/verify_orphans.py`) drops from **63% → <15%**. `pytest
backend/app/integrity/plugins/graph_extension/` green. Three unit tests, one
per extractor, on synthetic fixtures.

**Open knob.** Whether to upstream extractors to graphify proper or keep them
as a CCA-local post-pass. Default: post-pass first, evaluate upstreaming after
β ships.

### 5.2 B · `graph_lint` *(depends on A)*

**Problem solved.** Surface drift, dead-code candidates, and orphan growth
nightly with low false-positive rate by *intersecting* multiple signals.

**Checks (rule ids prefixed `graph.`):**

- `graph.dead_code` — Symbols flagged dead by **all three** of: vulture
  (`--min-confidence 80`), knip (frontend), graph orphan analysis (zero
  inbound EXTRACTED use-edges from A's enriched graph). Triple-intersection
  drives the false-positive rate near zero. Severity: WARN.
- `graph.drift_added` / `graph.drift_removed` — Nodes added/removed vs
  `graphify/graph.prev.json`. Severity: INFO.
- `graph.density_drop` — Per-module edge density falls >25% week-over-week.
  Often signals a refactor that broke import resolution. Severity: WARN.
- `graph.orphan_growth` — Unreferenced symbols spike >20% week-over-week.
  Severity: WARN.
- `graph.handler_unbound` — FastAPI handler with no `route → handler` edge
  (means decorator was removed but function lingers). Severity: WARN.

**Output.** `integrity-out/{date}/graph_lint.json` with full issue list.
Trend stored in `docs/health/trend.md` (rolling 30 days). Stores
`graph.prev.json` snapshot at scan end for next-night diff.

**Acceptance gate.** On a 20-item human-audited sample of `graph.dead_code`
issues, ≥80% are agreed dead. (Stricter than B's confidence band intentionally
— this is the gate that enables F to act.)

### 5.3 C · `doc_audit` *(depends on A)*

**Problem solved.** Docs reference a moving codebase; CLAUDE.md must index
everything in `docs/`; broken links erode trust silently.

**Checks (rule ids prefixed `doc.`):**

- `doc.unindexed` — File in `docs/` not linked from `CLAUDE.md` (transitively
  — links from a CLAUDE-linked doc count). Opt-out: `.claude-ignore` line per
  file. Severity: WARN. Fix class: `claude_md_link`.
- `doc.broken_link` — Relative link in `docs/**/*.md` that doesn't resolve
  (file or anchor). Severity: WARN. Fix class: `doc_link_renamed` (only when
  `git log --diff-filter=R` makes the rename unambiguous).
- `doc.dead_code_ref` — Doc references a `path:line` or `funcName` that no
  longer exists in the graph (uses A's enriched graph). Severity: WARN.
- `doc.stale_candidate` — Doc unchanged >90 days AND its referenced source
  files have changed since. Severity: INFO. (Information, not action — can't
  auto-detect "stale" reliably.)
- `doc.adr_status_drift` — ADR with `Status: accepted` references a function
  the code no longer calls / structure that no longer exists. Severity: WARN.

**Coverage rule.** `docs/` must contain at least one entry under each top-level
domain: `dev-setup.md`, `testing.md`, `gotchas.md`, `skill-creation.md`,
`log.md`. Missing → WARN, listed under `doc.coverage_gap`.

**Acceptance gate.** `make integrity-doc` exits 0 with: 100% of `docs/` reached
from CLAUDE.md; 0 broken intra-repo links.

### 5.4 E · `config_registry` *(no plugin deps)*

**Problem solved.** "Skills, scripts, Python functions, configs in one
observable place" — single inventory diffable across commits.

**Builds `config/manifest.yaml`** (committed) by walking the filesystem:

```yaml
generated_at: 2026-04-16T03:00:00Z
generator_version: 1.0.0

skills:
  - id: backend.app.skills.statistical_analysis.correlation.correlation_methodology
    skill_md: backend/app/skills/statistical_analysis/correlation/correlation_methodology/SKILL.md
    skill_yaml: backend/app/skills/statistical_analysis/correlation/correlation_methodology/skill.yaml
    entrypoints: [...]    # Python entrypoints from skill.yaml
    sha: <git blob sha of SKILL.md>

scripts:
  - path: scripts/verify_orphans.py
    interpreter: python3
    sha: <...>

routes:
  - method: POST
    path: /api/sessions/upload
    handler: backend.app.api.datasets_api.upload_dataset
    source: graph_extension      # provenance — came from A's extractor

configs:
  - path: pyproject.toml
    type: pyproject
    sha: <...>
  - path: .claude/settings.json
    type: claude_settings
    sha: <...>
  # ... package.json, vite.config.ts, Dockerfile*, Makefile, .env.example, etc.

functions:                       # Python entry-point functions only
  - id: backend.app.api.chat_api.chat_stream
    file: backend/app/api/chat_api.py
    line: 152
    decorators: ["@router.post"]
```

**Checks (rule ids prefixed `config.`):**

- `config.added` — New entry vs prior manifest. Severity: INFO.
- `config.removed` — Entry disappeared. Severity: INFO unless dependency
  graph shows it was still referenced → WARN.
- `config.schema_drift` — Config file `sha` changed AND structural diff shows
  schema-level change (not just value tweak). Severity: WARN. Detection: per
  config type, light schema validators in `plugins/config_registry/schemas/`.

**Acceptance gate.** Manifest covers every skill, script, FastAPI route
(via A), and config file in the project. Round-trip test:
add-test-fixture-config → scan → diff catches it. Skill count in manifest =
`SkillRegistry._index` size at runtime.

### 5.5 D · `hooks_check` *(depends on E)*

**Problem solved.** "Code changes trigger doc-update enforcement" — codify
which paths must have which hooks, then verify.

**Coverage rules** live in `config/hooks_coverage.yaml`:

```yaml
rules:
  - id: docs_changed_runs_link_check
    when: { paths: ["docs/**/*.md"] }
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit"
      command_substring: "doc_audit"
  - id: backend_changed_runs_typecheck
    when: { paths: ["backend/app/**/*.py"] }
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit"
      command_substring: "mypy"
  # ... five rules total at MVP
```

**Checks (rule ids prefixed `hooks.`):**

- `hooks.missing` — Coverage rule has no matching hook in
  `.claude/settings.json`. Severity: WARN.
- `hooks.broken` — Configured hook command exits non-zero in dry-run
  (uses sample input). Severity: WARN.
- `hooks.unused` — Hook configured but no coverage rule justifies it.
  Severity: INFO.

**Acceptance gate.** Five coverage rules defined for the highest-churn paths
(determined from `git log --since='30 days ago' --name-only` analysis).
Every rule has a configured hook. Every hook dry-runs green.

### 5.6 F · `autofix` *(depends on B, C, E)*

**Problem solved.** Mechanical drift gets fixed without the user having to
remember; risky fixes never get attempted.

**Whitelist of fix classes** (anything not listed is HUMAN-ONLY):

| Fix class | Source rule | What it does |
|-----------|-------------|--------------|
| `claude_md_link` | `doc.unindexed` | Add a single `- [Title](relative/path.md)` line to the appropriate section of `CLAUDE.md` |
| `doc_link_renamed` | `doc.broken_link` | Rewrite link target when `git log --diff-filter=R --follow` shows an unambiguous rename |
| `manifest_regen` | `config.added`/`removed` | Regenerate `config/manifest.yaml` (mechanical) |
| `dead_directive_cleanup` | n/a (driven by lint output) | Remove `# noqa: <code>` / `// eslint-disable-next-line <rule>` for issues that no longer trigger |
| `health_dashboard_refresh` | n/a | Regenerate `docs/health/latest.md` + `trend.md` |

**Hard rules:**

- Never modifies code logic. Never deletes files. Never auto-commits to main.
- Each fix class → its own PR, title `chore(integrity): <fix_class>`,
  body lists the underlying issues + their `evidence` fields.
- PR opened against a fresh branch `integrity/autofix/<fix_class>/<date>`.
- Concurrency: at most one open autofix PR per fix class. Update existing
  PR rather than opening duplicates.
- Skip the run entirely if any upstream plugin failed (don't act on a
  partial picture).

**Acceptance gate.** In a 1-week trial, ≥1 auto-PR per fix class merges with
zero human edits. If a fix class produces a PR that requires human edits >2
times in a month, it's auto-disabled and the rule moves to HUMAN-ONLY.

## 6. Data flow

```
trigger
  ├── nightly cron (GitHub Actions, 03:00 UTC)
  ├── POST /api/health/run (manual or PR comment "/integrity")
  └── PostToolUse hook on Edit/Write under docs/ or backend/app/
        ↓
IntegrityEngine.discover()
        ↓                 (load enabled plugins from config/integrity.yaml)
topological run order: A → {B, C, D, E parallel} → F
        ↓
each plugin: scan(ctx) → list[IntegrityIssue]
        ↓
aggregate → IntegrityReport
        ↓
write integrity-out/{ISO-date}/report.{json,md}    (gitignored)
write docs/health/latest.md                         (committed via autofix's
                                                     health_dashboard_refresh)
        ↓
if autofix enabled and any issue.fix_class set:
        group by fix_class → one PR per class (or update existing PR)
        ↓
frontend GET /api/health → renders latest report
```

## 7. Sequencing roadmap (deep-first gates)

No calendar dates. Each gate is a hard go/no-go: don't start the next phase
until the previous gate passes for **7 consecutive nightly runs**.

| Phase | Sub-projects | Gate |
|-------|-------------|------|
| **α** | engine + plugin **A** | False-positive orphan rate <15% backend / <30% frontend on 100-symbol audit; A's edges in `graphify/graph.augmented.json` with `extension: "cca-v1"`; `pytest backend/app/integrity/` green |
| **β** | plugin **B** + frontend Health (skeleton) | Nightly diff produces report; on a 20-item `graph.dead_code` sample, ≥80% are agreed dead; Health section renders B's output |
| **γ** | plugin **C** | 100% of `docs/` reached from CLAUDE.md; 0 broken intra-repo links; ADR drift check runs on all `knowledge/adr/*.md` |
| **δ** | plugin **E** | Manifest covers every skill / script / route / config; round-trip add-then-scan test passes |
| **ε** | plugin **D** | 5 coverage rules defined, all have configured hooks, all dry-run green |
| **ζ** | plugin **F** | ≥1 auto-PR per fix class merges with 0 human edits in a 1-week trial |

Frontend integration:
- α end → Health stub (renders `docs/health/latest.md` raw)
- β → live data via `/api/health`
- γ onward → per-plugin drill-down + filter UI

## 8. Error handling

- Plugin exception caught at engine level → `IntegrityIssue(severity=ERROR,
  source="<plugin>.scan", message=<exception>)`. Other plugins continue.
- Partial reports are valid. Frontend shows per-plugin badge: `ok | failed |
  skipped | stale`.
- Plugin marked `failed` for **3 consecutive nightly runs** auto-disables
  itself (set `enabled: false` in `config/integrity.yaml`) and opens a single
  rolling issue. Don't let one broken plugin take down the dashboard.
- Autofix never operates on a partial report. If any upstream plugin failed,
  autofix logs `skipped: upstream_failure` and exits clean.
- Engine-level failure (can't load plugins, can't write report) → fail loud
  via cron → opens a `[integrity-engine] failure` issue. This is the only
  CRITICAL severity used.

## 9. Testing

- **Unit per plugin**: `backend/app/integrity/plugins/<name>/tests/test_*.py`
  with synthetic fixture repos (`tests/fixtures/<name>/`). Assert exact issue
  list. Each rule has at least one positive and one negative fixture.
- **Integration**: `test_engine_pipeline.py` runs the full pipeline on a tiny
  fixture project; asserts report shape, dependency ordering, and that a
  failed plugin doesn't crash siblings.
- **Golden snapshot**: `test_real_repo_smoke.py` runs against a frozen copy of
  `claude-code-agent` itself (committed under `tests/fixtures/repo-snapshot/`,
  refreshed manually quarterly). Asserts issue count is within ±10% of golden.
  This catches regressions in the integrity system itself.
- **No 80% coverage rule**: replaced with the per-phase **acceptance gates**
  in §7. This is a measurement system; what matters is that the measurements
  are correct, not that every internal helper has a test.

## 10. Spec lifecycle

- **Mega-spec** (this document): single source of truth for the umbrella +
  sub-projects A–F. Versioned in place — no v2/v3 sibling files. Bump
  `last_revised` on edit.
- **Sub-specs**: when a phase starts, spawn
  `docs/superpowers/specs/2026-04-XX-integrity-<plugin>-design.md` via
  /brainstorming → /writing-plans for that plugin specifically. The mega-spec
  `sub_specs:` front-matter list gets the new path.
- **Self-maintenance**: once plugin C ships (γ), it scans these sub-specs
  alongside other docs. Stale spec (referenced symbol no longer exists,
  status `shipped` but code shows otherwise) → flagged in the next nightly run.
  The system watches its own design.
- **Closure**: when a sub-project's gate passes for 7 consecutive nightly
  runs, mark its sub-spec `Status: shipped` in the front matter. Do not
  delete (Phase 10 cleanup applies only to *plans*, not specs — design intent
  remains queryable).
- **Deprecation**: if a plugin is removed, change its sub-spec front matter
  to `Status: deprecated` with a `replaced_by:` pointer; keep the file.

## 11. Operational defaults

| Setting | Default | Where to change |
|---------|---------|-----------------|
| Cron schedule | `0 3 * * *` (03:00 UTC nightly) | `.github/workflows/integrity.yml` |
| Enabled plugins | All six | `config/integrity.yaml` |
| Autofix enabled | `false` until ζ ships | `config/integrity.yaml` |
| Report retention | 30 days | `config/integrity.yaml` (storage cleanup hook) |
| Health endpoint auth | Same as `/api/sessions` | Reuse existing auth middleware |
| PostToolUse incremental triggers | Off until α gate passes | `.claude/settings.json` |
| Failed-run notification | Open GitHub issue | Cron workflow uses `gh issue create` |

## 12. Open questions (resolve in sub-specs)

- **A**: Upstream graphify extractors or keep CCA-local? Default: local first,
  re-evaluate after β.
- **B**: Should `graph.density_drop` look at module-level or whole-graph
  density? Default: module — whole-graph is too noisy.
- **C**: Does `doc.stale_candidate` warrant a `fix_class` (e.g. add a
  `<!-- last-reviewed: 2026-04-16 -->` marker)? Default: no (information only).
- **D**: Where do "coverage rules" live — `config/hooks_coverage.yaml` (this
  spec's choice) or inline in `.claude/settings.json` extension fields?
  Default: separate file, easier to lint.
- **E**: Manifest stored as YAML or DuckDB table? Default: YAML for
  diff-ability; revisit if it grows past ~5MB.
- **F**: First fix class to enable in production? Recommend `manifest_regen`
  (lowest risk).

## 13. References

- `docs/log.md` — Phase 9.3 finding that motivated this work
- `progress.md` — Phase 9.3 + Phase 10 conclusions
- `~/.claude/skills/graphify/SKILL.md` — graphify pipeline this builds on
- `CLAUDE.md` — project conventions, existing make targets
- `knowledge/adr/` — architecture decision records (will become a
  `doc_audit` target)
