# Plugin B — Graph Lint (gate β)

**Status:** design / ready for plan
**Parent:** [`2026-04-16-integrity-system-design.md`](./2026-04-16-integrity-system-design.md) §5.2
**Predecessor:** [`2026-04-16-integrity-plugin-a-design.md`](./2026-04-16-integrity-plugin-a-design.md) (gate α — shipped, FP 37.8% backend / 34.2% frontend)
**Date:** 2026-04-17

---

## 1. Goal

Ship gate β:

- `graph_lint` plugin emits 5 rule classes from intersected dead-code signals + day-over-day & week-over-week graph diffs.
- The integrity engine becomes the real orchestrator: auto-merges A's `graph.augmented.json`, dispatches plugins in dependency order, aggregates a unified report.
- Frontend gets a discoverable Health page that renders `docs/health/latest.md` raw — proves the data path end-to-end without committing to per-plugin UI yet.

**Acceptance gate (β):** Manual 20-item dead-code audit at ≥80% agreement (≥16/20 verified-dead). One full `make integrity` run produces all required artifacts. All `backend/tests/integrity/` tests pass.

## 2. Non-goals

- No `/api/health` JSON endpoint — γ ships the live API.
- No per-plugin cards, sparklines, issue table, run-scan button — γ.
- No autofix — ζ.
- No nightly cron, scheduler, or CI integration — operations work, separate from the plugin contract.
- No `dismiss` flow / persisted ignores beyond `config/integrity.yaml::ignored_dead_code:`.

## 3. Operating model (decisions locked from brainstorm)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dead-code signal | **Triple-intersect** vulture + knip + graph orphans | Spec §5.2 requires it; intersection is what drives FP near zero. Adding two well-maintained dev-tools is cheap. |
| Frontend Health scope | **Page + sidebar rail entry only**, renders `docs/health/latest.md` raw | Per parent §7: "α end → Health stub (renders `docs/health/latest.md` raw)". Stubbed cards would be dead UI. |
| Engine wiring | **Promote engine to first-class.** `GraphSnapshot.load` auto-merges augmented; engine dispatches A→B; new module CLI `python -m backend.app.integrity` | β is the right time to make the engine real — γ/δ/ε/ζ all assume it exists. Wire once. |
| Snapshot strategy | **Dated history under `integrity-out/snapshots/{date}.json`**, gitignored, 30-day retention | WoW rules need 7-day baselines; trend.md needs 30-day window. Local-only disk cost (~90 MB). |
| Dead-code audit | **Manual one-shot**, results in `docs/health/audit-2026-04-17.md` | Gate is a one-time event for β; script-ify only if/when we re-audit. |
| Thresholds | **`config/integrity.yaml`**, env-overridable per parent §4.3 | Tunable without code change; visible in PRs. |
| `density_drop` scope | **Per-module** (parent §12 default) | Whole-graph is too noisy; per-module localizes the signal. |

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CLI: python -m backend.app.integrity (or `make integrity`) │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  IntegrityEngine                                            │
│   1. GraphSnapshot.load()                                   │
│      reads graph.json + auto-merges graph.augmented.json    │
│   2. Dispatches plugins in dependency order:                │
│      graph_extension (A) → graph_lint (B)                   │
│   3. Aggregates ScanResults → integrity-out/{date}/report.* │
│   4. Snapshots merged graph → integrity-out/snapshots/      │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ graph_extension (A)      │    │ graph_lint (B)           │
│  emits graph.augmented   │    │  reads merged graph      │
│  (already shipped)       │    │  + diffs vs snapshots/   │
│                          │    │  + runs vulture, knip    │
│                          │    │  → graph_lint.json       │
│                          │    │  → docs/health/latest.md │
│                          │    │  → docs/health/trend.md  │
└──────────────────────────┘    └──────────────────────────┘
```

### 4.1 New / modified files

| Path | Status | Purpose |
|------|--------|---------|
| `backend/app/integrity/engine.py` | **modify** | Add `register_default_plugins()`, dependency-ordered dispatch, error catching per parent §8 |
| `backend/app/integrity/schema.py` | **modify** | `GraphSnapshot.load` auto-merges `graph.augmented.json` (links/nodes from augmented win on duplicate `id`) |
| `backend/app/integrity/snapshots.py` | **new** | `write_snapshot(graph, date)`, `load_snapshot_by_age(days)`, `prune_older_than(days)` |
| `backend/app/integrity/report.py` | **new** | Collapses `ScanResult`s → `report.json` + `report.md` + `docs/health/latest.md` + appends `docs/health/trend.md` |
| `backend/app/integrity/__main__.py` | **new** | Module CLI `python -m backend.app.integrity [--plugin <name>] [--no-augment]` |
| `backend/app/integrity/plugins/graph_lint/__init__.py` | new | Package marker |
| `backend/app/integrity/plugins/graph_lint/plugin.py` | new | `GraphLintPlugin` dataclass; `scan()` orchestrates rules |
| `backend/app/integrity/plugins/graph_lint/rules/dead_code.py` | new | Triple-intersection logic |
| `backend/app/integrity/plugins/graph_lint/rules/drift.py` | new | Added/removed node diff |
| `backend/app/integrity/plugins/graph_lint/rules/density_drop.py` | new | Per-module WoW density compare |
| `backend/app/integrity/plugins/graph_lint/rules/orphan_growth.py` | new | Whole-graph WoW orphan compare |
| `backend/app/integrity/plugins/graph_lint/rules/handler_unbound.py` | new | FastAPI route w/o handler edge |
| `backend/app/integrity/plugins/graph_lint/wrappers/vulture.py` | new | Subprocess + JSON parse |
| `backend/app/integrity/plugins/graph_lint/wrappers/knip.py` | new | Subprocess + JSON parse |
| `backend/app/integrity/plugins/graph_lint/config.py` | new | Loads thresholds from `config/integrity.yaml` |
| `config/integrity.yaml` | new | Engine config (committed) |
| `frontend/src/routes/health.tsx` (path TBD by routing convention) | new | Page renders `docs/health/latest.md` |
| `frontend/src/components/sidebar/...` | modify | Add Health rail entry |
| `Makefile` | modify | Add `integrity:` target (full pipeline); `integrity-lint:` (B only) |
| `.gitignore` | modify | Add `integrity-out/` |
| `pyproject.toml` (or `backend/pyproject.toml`) | modify | Add `vulture` to dev deps |
| `frontend/package.json` | modify | Add `knip` to devDependencies |

### 4.2 Plugin contract

`GraphLintPlugin` conforms to existing `IntegrityPlugin` Protocol:

```python
@dataclass
class GraphLintPlugin:
    name: str = "graph_lint"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("graph_extension",)
    paths: tuple[str, ...] = (
        "backend/app/**/*.py",
        "frontend/src/**/*.{ts,tsx,js,jsx}",
        "graphify/graph.json",
        "graphify/graph.augmented.json",
    )

    def scan(self, ctx: ScanContext) -> ScanResult:
        ...
```

`ctx.graph` already merged by engine. Plugin returns `ScanResult` with `issues` (in-memory, list of dicts matching the output shape in §5.6) and `artifacts` (list of `Path`s including `integrity-out/{today}/graph_lint.json`).

## 5. The five rules

### 5.1 `graph.dead_code`

**Signal.** Symbol/file flagged dead by **all three** of:
- vulture (`vulture backend/app --min-confidence 80 --json`) — Python side.
- knip (`cd frontend && npx knip --reporter json`) — TS/JS side.
- Graph orphan analysis on the merged augmented graph (zero inbound `EXTRACTED` edges in `imports_from`, `calls`, `implements`, `extends`, `instantiates`, `uses`, `references`, `decorated_by`, `raises`, `returns`).

**Triple-intersection logic.**
- For each Python `node_id`: emit if `vulture_dead(symbol) AND graph_orphan(node_id)`.
- For each TS/JS `node_id`: emit if `knip_dead(file_or_export) AND graph_orphan(node_id)`.
- Cross-tier: a Python symbol is never matched against knip; a TS export never against vulture. The "triple" is **(language-side tool) + (graph orphan signal) + (the rule itself confirming both)** — vulture/knip individually have FPs that graph orphan analysis catches, and vice versa.

**Severity.** WARN.
**Fix class.** `delete_dead_code`.
**Ignore mechanisms.**
- `# noqa: dead-code` line comment in source (Python).
- `// knip-ignore` line comment (TS/JS).
- `config/integrity.yaml::ignored_dead_code: [<node_id>, ...]`.

### 5.2 `graph.drift_added`

**Signal.** Node ID present in today's snapshot, absent from yesterday's snapshot.
**Excludes.** Paths matching `config/integrity.yaml::excluded_paths` (default: `tests/**`, `**/migrations/**`, `**/__pycache__/**`).
**Severity.** INFO. Information only — adds are usually intentional.
**Fix class.** None.

### 5.3 `graph.drift_removed`

**Signal.** Node ID present in yesterday's snapshot, absent from today's.
**Excludes.** Same as `drift_added`.
**Severity.** INFO when paired with a matching `git log --diff-filter=R` entry within the last 24h (file-rename detected); WARN otherwise (silent removal).
**Fix class.** None (informational).

### 5.4 `graph.density_drop`

**Signal.** For each Python module (file):
- `today_ratio = today_intra_module_edges / today_module_nodes`.
- `wow_ratio = wow_intra_module_edges / wow_module_nodes` from snapshot 7 days ago.
- Emit if `today_ratio < 0.75 × wow_ratio` (i.e. >25% drop).

**Excludes.** Modules with <`module_min_nodes` (default 5) on either side. Modules absent in 7d-old snapshot (newly added) skip evaluation.
**Severity.** WARN.
**Fix class.** None (signal for human review — usually a refactor that broke import resolution).

### 5.5 `graph.orphan_growth`

**Signal.** `today_orphan_count > 1.20 × wow_orphan_count` from snapshot 7 days ago. Single global signal.
**Severity.** WARN.
**Fix class.** None.
**Insufficient-history behavior.** If 7d-old snapshot missing, emit one INFO `graph.orphan_growth.no_baseline` and skip.

### 5.6 `graph.handler_unbound`

**Signal.** FastAPI handler function (any node with `kind == "function"` whose `source_file` matches `backend/app/api/**/*.py` or `backend/app/harness/**/*.py` and whose name does not start with `_`) that has no inbound `routes_to` edge in the merged graph.
**Excludes.** Functions decorated with `@pytest.fixture`, `@pytest.mark.*`. Functions in `tests/`.
**Severity.** WARN.
**Fix class.** None (usually a stale handler whose decorator was removed; needs human triage).

### 5.7 Issue output shape

```json
{
  "rule": "graph.dead_code",
  "severity": "WARN",
  "node_id": "datasets_api_purge_old",
  "location": "backend/app/api/datasets_api.py:147",
  "message": "Symbol unreferenced (vulture+knip+graph triple-confirm)",
  "evidence": {"vulture": true, "knip": false, "graph_orphan": true},
  "fix_class": "delete_dead_code",
  "first_seen": "2026-04-17"
}
```

`first_seen` set on initial detection; preserved across runs by reading the previous `report.json` and matching on `(rule, node_id)`.

## 6. Data flow

**Per-run sequence.**

1. `python -m backend.app.integrity` (or `make integrity`).
2. Engine boots; loads `config/integrity.yaml`.
3. `GraphSnapshot.load(repo_root)` reads `graphify/graph.json`, then if `graphify/graph.augmented.json` exists, merges its nodes/links (augmented wins on duplicate `id` for nodes; links concatenated with dedupe on `(source, target, relation)`).
4. Plugin A (`graph_extension`) `scan()` — refreshes `graph.augmented.json` (idempotent).
5. Plugin B (`graph_lint`) `scan()`:
   - Load 1d-old snapshot from `integrity-out/snapshots/{today-1}.json` → drift.
   - Load 7d-old snapshot from `integrity-out/snapshots/{today-7}.json` → density_drop, orphan_growth.
   - Subprocess `vulture` + parse JSON; subprocess `knip` + parse JSON.
   - Compute graph orphans on the merged graph (use the same definition as `verify_orphans.py` post-rewrite — exclude tests, entry points, etc.).
   - Intersect for `dead_code`.
   - Walk merged graph for `handler_unbound`.
   - Write `integrity-out/{today}/graph_lint.json`.
6. Engine `report.write()`:
   - Collapse all plugin `ScanResult`s into one `IntegrityReport`.
   - Write `integrity-out/{today}/report.json` + `report.md`.
   - Write `docs/health/latest.md` (committed) — per-plugin sections with anchors, counts by severity, links into per-plugin artifacts.
   - Append today's row(s) to `docs/health/trend.md`, trim rows older than 30 days.
   - Write `integrity-out/snapshots/{today}.json` (full merged graph copy).
   - Prune `integrity-out/snapshots/*.json` older than 30 days.
   - Update `integrity-out/latest -> {today}/` symlink.

## 7. Storage layout

| Path | Tracked? | Purpose |
|------|----------|---------|
| `integrity-out/{date}/report.json` | gitignored | Full machine-readable report |
| `integrity-out/{date}/report.md` | gitignored | Human-readable mirror |
| `integrity-out/{date}/graph_lint.json` | gitignored | B's raw output |
| `integrity-out/snapshots/{date}.json` | gitignored | Daily merged graph; 30-day window |
| `integrity-out/latest -> {date}/` | gitignored symlink | Convenience pointer |
| `docs/health/latest.md` | committed | Frontend renders this |
| `docs/health/trend.md` | committed | 30-day rolling counts (per-plugin × severity) |
| `docs/health/audit-2026-04-17.md` | committed | Gate β manual dead-code audit results |
| `config/integrity.yaml` | committed | Engine + thresholds + ignores |

`integrity-out/` is added to `.gitignore`.

## 8. Configuration

`config/integrity.yaml` (committed; this is the only committed source of thresholds):

```yaml
plugins:
  graph_extension:
    enabled: true
  graph_lint:
    enabled: true
    thresholds:
      vulture_min_confidence: 80      # passed to vulture --min-confidence
      density_drop_pct: 25            # >25% WoW drop → WARN
      orphan_growth_pct: 20           # >20% WoW growth → WARN
      module_min_nodes: 5             # density_drop ignores smaller modules
      snapshot_retention_days: 30     # prune older snapshots
    ignored_dead_code: []             # list of node_ids
    excluded_paths:
      - "tests/**"
      - "**/migrations/**"
      - "**/__pycache__/**"
```

Env override per parent §11: `INTEGRITY_<KEY>=<value>` reads override the YAML at load time (e.g. `INTEGRITY_VULTURE_MIN_CONFIDENCE=70 make integrity`).

## 9. Frontend Health skeleton

**Single new route + sidebar rail entry.** Reuses existing markdown rendering and sidebar patterns — no new design system work.

**Pieces.**
- `frontend/src/routes/health.tsx` (or matching the project's routing convention, confirmed at planning) — fetches `docs/health/latest.md` via the existing static-asset path, renders via the existing markdown component used for chat/docs.
- Sidebar icon rail — add `Health` entry between `Context` and `Terminal` per parent §4.5 ordering.
- Empty state when `latest.md` is missing: *"No integrity report yet. Run `make integrity` to generate one."*

**Out of scope (γ).**
- `/api/health` JSON endpoint
- Per-plugin cards, sparklines, issue table, trend live-render
- Run-scan button

**Discoverability test.** From a fresh `make dev`, a developer can click the Health rail entry, see today's run summary, and follow links from `latest.md` into per-plugin sections rendered as anchored markdown.

## 10. Error handling

- Per parent §8: any plugin exception → caught at engine, recorded as `IntegrityIssue(severity=ERROR, source="<plugin>.scan", message=<exception>)`. Sibling plugins continue.
- vulture / knip subprocess failure → recorded under `failures` in `ScanResult`; dead_code emits zero issues for that side; drift / density / orphan / handler rules continue.
- Missing 7d-old snapshot (first runs before history exists) → density_drop and orphan_growth emit one INFO each (`*.no_baseline`) and skip evaluation.
- Missing 1d-old snapshot → drift_added/drift_removed emit one INFO `graph.drift.no_baseline` and skip.
- Engine-level failure (can't load config, can't write report) → fail loud with exit code 1; surfaced via cron in operations.

## 11. Testing

- **Per-rule unit tests** (`backend/tests/integrity/plugins/graph_lint/`):
  - `test_dead_code_triple_intersection.py` — synthetic vulture/knip fixtures + tiny graph; verify only triple-confirmed survive.
  - `test_drift.py` — two synthetic snapshots; assert added/removed; verify rename downgrade to INFO.
  - `test_density_drop.py` — module density falls 30% → WARN; falls 10% → no issue; module with 4 nodes → no issue.
  - `test_orphan_growth.py` — same shape.
  - `test_handler_unbound.py` — synthetic graph with + without `routes_to` edge.
  - `test_snapshots.py` — write/load/prune correctness; missing-baseline behavior.
- **Engine integration** (`backend/tests/integrity/`):
  - `test_engine_pipeline.py` — full A→B against a tiny fixture repo; asserts `report.json` shape, dependency order, augmented merge happens.
  - `test_graph_snapshot_merge.py` — verify auto-merge; ID-collision precedence (augmented wins); link dedupe.
  - `test_report_writer.py` — writes `latest.md`, appends `trend.md`, prunes old rows.
- **Frontend.** One Playwright (or equivalent existing E2E) test asserts the Health rail entry navigates to `/health` (or whatever path) and renders content from `docs/health/latest.md`.

## 12. Acceptance gate (β)

All must hold:

1. `make integrity` exits 0 against the live repo.
2. Produces `integrity-out/{today}/report.json`, `report.md`, `graph_lint.json`, `snapshots/{today}.json`, `docs/health/latest.md`, and appends to `docs/health/trend.md`.
3. All `backend/tests/integrity/` tests pass.
4. `docs/health/audit-2026-04-17.md` documents the manual review of 20 sampled `graph.dead_code` issues, with per-issue verified-dead/false-positive marks. **Gate passes if ≥16/20 (80%) verified-dead.**
5. Frontend Health page renders `latest.md`; rail entry visible from `make dev`.

If gate (4) fails: tighten one of {`vulture_min_confidence`, knip config, `excluded_paths`} and re-audit. Don't lower the gate.

If the live run produces fewer than 5 dead_code issues: gate (4) is N/A for this run. Re-run with `INTEGRITY_VULTURE_MIN_CONFIDENCE=60` to surface a denser sample for one-time audit.

## 13. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Triple-intersection too strict, ~0 issues found on small repo | Min-5-issue gate threshold; `INTEGRITY_VULTURE_MIN_CONFIDENCE` env override for one-off audit runs. |
| vulture / knip slow CI/local | Both run only on `make integrity` (manual or nightly). Not wired to pre-commit. |
| Snapshot disk growth (~3MB × 30 = ~90MB) | Local-only (gitignored). Auto-prune at write time. |
| `docs/health/latest.md` churn pollutes git log | Committed deliberately per parent §4.3. The signal-vs-noise tradeoff favors visibility. Revisit if log review becomes painful. |
| Augmented merge precedence wrong (base node attributes overwritten) | Tests cover this. Augmented wins for nodes with same `id`; base preserved for IDs only in base. |
| Open: where exactly does the frontend route mount (`/health` vs nested under `/devtools`)? | Resolve at planning; defer to project's existing routing convention. |

## 14. References

- `docs/superpowers/specs/2026-04-16-integrity-system-design.md` — parent system design (gate β = §5.2 + §4.5 + §7).
- `docs/superpowers/specs/2026-04-16-integrity-plugin-a-design.md` — predecessor (gate α).
- `scripts/verify_orphans.py` — orphan-definition baseline reused in `dead_code` graph signal.
- vulture: <https://github.com/jendrikseipp/vulture>
- knip: <https://knip.dev>
