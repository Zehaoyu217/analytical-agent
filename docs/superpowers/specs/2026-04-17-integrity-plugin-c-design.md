---
title: Integrity Plugin C (doc_audit) — gate γ
status: design-approved
created: 2026-04-17
last_revised: 2026-04-17
owner: jay
parent_spec: 2026-04-16-integrity-system-design.md
gate: γ
depends_on:
  - 2026-04-16-integrity-plugin-a-design.md   # gate α — shipped
  - 2026-04-17-integrity-plugin-b-design.md   # gate β — shipped (engine + report aggregator)
---

# Plugin C — `doc_audit`

> Sub-spec for gate γ of the integrity system. Parent: `2026-04-16-integrity-system-design.md` §5.3. This document is the single source of truth for Plugin C's scope, design, and acceptance criteria. Edit in place; bump `last_revised`.

## 1. Goal

Surface markdown drift in `claude-code-agent` nightly:
1. Docs not reachable from `CLAUDE.md` (knowledge silently orphaned).
2. Broken intra-repo links (file rename / move broke a reference).
3. Doc references to symbols/files that no longer exist in the codebase.
4. Stale docs that haven't been touched while their referenced source has moved.
5. ADRs marked `Status: Accepted` whose decision references vanished code.
6. `docs/` top-level coverage gaps (no `dev-setup.md`, `testing.md`, etc.).

All checks build on Plugin A's enriched graph (`graphify/graph.augmented.json`) and the engine + aggregator shipped at gate β. No code-modification: detection only. Autofix is gate ζ (Plugin F).

## 2. Non-goals

- Semantic doc bugs ("this paragraph is wrong"). Only mechanical/structural drift.
- Full markdown linting (heading levels, line length, etc.). Out of scope — `make wiki-lint` already handles wiki-specific lint.
- Cross-repo link checking. Only intra-repo links are validated.
- Editing CLAUDE.md or any markdown file. Plugin C reports; gate ζ acts.

## 3. Decisions locked from brainstorm

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Markdown parser | `markdown-it-py` (CommonMark + GFM tables/anchors) | De facto standard, MIT, Jupyter-tested, real AST |
| Reachability root | Configurable list `seed_docs` (default `["CLAUDE.md"]`) | Future-proof for README.md / per-area indexes |
| Coverage list | Configurable in `config/integrity.yaml` (default per parent §5.3) | Avoid hardcoding; project conventions evolve |
| Stale threshold | 90 days, configurable | Per parent §5.3 |
| ADR Status format | Both `**Status:** Accepted` (bold line) and YAML front matter `status: accepted` | Today's ADRs use the bold form; future-proof for migration |
| Doc roots | `docs/**/*.md`, `knowledge/**/*.md`, repo-root `*.md` | Catches CLAUDE.md, README.md, ADRs, wiki |
| Excluded paths | `reference/**`, `node_modules/**`, `**/__pycache__/**`, `integrity-out/**`, `docs/health/**` (generated), `docs/superpowers/**` (specs/plans, separate domain) | Reduces noise; configurable |
| Path/symbol extraction | Conservative — backticked `` `path/to/file.py` ``, `` `path/to/file.py:42` ``, `` `funcName` ``, `` `Module.funcName` `` only | Free-form prose extraction creates false positives |
| Anchor slug | GitHub-style (lowercase, hyphens, strip non-alphanumeric except `-`) | Matches GitHub render; ADR/doc anchors are GitHub-readable |
| Git-rename lookback | 30 days, configurable | Matches Plugin B pattern; renames older than that = stale signal anyway |
| Plugin output | `integrity-out/{date}/doc_audit.json` | Mirrors Plugin B's per-plugin artifact pattern |
| `.claude-ignore` | One path-glob per line; per-doc opt-out | Matches `.gitignore` conventions; future-proof for per-domain rules |

## 4. Architecture

### 4.1 File layout

```
backend/app/integrity/plugins/doc_audit/
  __init__.py
  plugin.py                          # DocAuditPlugin (mirrors GraphLintPlugin shape)
  rules/
    __init__.py
    unindexed.py                     # doc.unindexed
    broken_link.py                   # doc.broken_link (+ rename downgrade)
    dead_code_ref.py                 # doc.dead_code_ref
    stale_candidate.py               # doc.stale_candidate (INFO)
    adr_status_drift.py              # doc.adr_status_drift
    coverage_gap.py                  # doc.coverage_gap
  parser/
    __init__.py
    markdown.py                      # markdown-it-py wrapper
    code_refs.py                     # path:line + backticked-symbol regex
    git_log.py                       # last-commit timestamp helper (per-scan cache)
    ignore.py                        # .claude-ignore loader (gitignore-style globs)
  tests/
    __init__.py
    conftest.py                      # tiny_repo fixture builder
    fixtures/
      tiny_repo/                     # synthetic mini-repo, ~10 files
        CLAUDE.md
        docs/
          dev-setup.md
          testing.md
          gotchas.md
          skill-creation.md
          log.md
          orphan.md                  # NOT linked from CLAUDE.md → unindexed
          broken.md                  # links to gone.md → broken_link
          dead-ref.md                # references missing-symbol → dead_code_ref
          stale.md                   # 91 days old + ref'd src changed → stale_candidate
        knowledge/adr/
          001-real.md                # Accepted, refs live code → no issue
          002-drift.md               # Accepted, refs gone code → adr_status_drift
        backend/app/foo.py
        graphify/graph.json
        graphify/graph.augmented.json
        .claude-ignore               # opt-out lines
    test_unindexed.py
    test_broken_link.py
    test_dead_code_ref.py
    test_stale_candidate.py
    test_adr_status_drift.py
    test_coverage_gap.py
    test_parser_markdown.py
    test_parser_code_refs.py
    test_parser_git_log.py
    test_parser_ignore.py
    test_plugin_integration.py
```

### 4.2 Plugin shape

Mirrors `GraphLintPlugin`:

```python
@dataclass
class DocAuditPlugin:
    name: str = "doc_audit"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("graph_extension",)
    paths: tuple[str, ...] = (
        "docs/**/*.md",
        "knowledge/**/*.md",
        "CLAUDE.md",
        "*.md",
    )
    config: dict[str, Any] = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    rules: dict[str, Rule] | None = None

    def scan(self, ctx: ScanContext) -> ScanResult:
        # Same per-rule try/except pattern as GraphLintPlugin.
        # On rule exception → IntegrityIssue(severity=ERROR), siblings continue.
        # Writes integrity-out/{date}/doc_audit.json with rules_run + failures + issues.
```

### 4.3 Rule signature

Reuse Plugin B's `Rule` type:

```python
Rule = Callable[[ScanContext, dict[str, Any], date], list[IntegrityIssue]]
```

Each rule receives the `ScanContext` (with `repo_root` and `GraphSnapshot`), the plugin config dict, and today's date. Returns a list of `IntegrityIssue`.

### 4.4 Parser layer

**`parser/markdown.py`** — Pre-parses every doc once per scan, returns:

```python
@dataclass(frozen=True)
class ParsedDoc:
    path: Path                        # absolute
    rel_path: str                     # relative to repo_root, posix-style
    headings: list[Heading]           # for anchor index
    links: list[MarkdownLink]         # all links found
    code_refs: list[CodeRef]          # path:line + symbol mentions in backticks
    front_matter: dict[str, Any]      # parsed YAML front matter (or {})
    raw_text: str                     # for status-line ADR detection

@dataclass(frozen=True)
class Heading:
    text: str
    slug: str                         # GitHub-style
    level: int

@dataclass(frozen=True)
class MarkdownLink:
    target: str                       # raw href
    anchor: str | None                # parsed from #section
    text: str
    line: int                         # source line of the link

@dataclass(frozen=True)
class CodeRef:
    text: str                         # `path` or `path:line` or `funcName`
    kind: Literal["path", "path_line", "symbol"]
    path: str | None                  # for path / path_line
    line: int | None                  # for path_line
    symbol: str | None                # for symbol
    source_line: int                  # line in the doc
```

`MarkdownIndex` (built once, shared across rules):

```python
@dataclass(frozen=True)
class MarkdownIndex:
    docs: dict[str, ParsedDoc]                   # rel_path → ParsedDoc
    anchors_by_path: dict[str, set[str]]         # rel_path → set of slugs
    link_graph: dict[str, set[str]]              # rel_path → set of target rel_paths
    excluded: frozenset[str]                     # rel_paths matching excluded_paths
    ignored: frozenset[str]                      # rel_paths matching .claude-ignore
```

**`parser/code_refs.py`** — Conservative extraction. Patterns (Python regex):

```
PATH_LINE  = r"`([\w./\-]+\.[a-z]{1,5}):(\d+)`"
PATH       = r"`([\w./\-]+/[\w./\-]+\.[a-z]{1,5})`"   # must contain `/`
SYMBOL     = r"`([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)`"
```

`SYMBOL` matches conservatively (returns to caller for graph lookup; not flagged unless caller decides). Path patterns require a file extension.

**`parser/git_log.py`** — `last_commit_iso(rel_path: str) -> str | None`. Cached per scan via `lru_cache(maxsize=None)` on a fresh helper instance.

**`parser/ignore.py`** — Loads `.claude-ignore` (path-glob per line, `#` comments, blank lines ignored). Returns a matcher. Falls back to empty matcher if file absent.

### 4.5 Rules in detail

#### `doc.unindexed`

1. Build `link_graph` from MarkdownIndex (only md→md links count).
2. BFS from each `seed_docs` entry (default `CLAUDE.md`). Record visited.
3. For each doc in scope (`doc_roots` ∩ ¬`excluded_paths` ∩ ¬`ignored`):
   - If not visited → emit `IntegrityIssue(rule="doc.unindexed", severity="WARN", node_id=rel_path, location=rel_path, message=f"Not reachable from {seed_docs}", evidence={"seed_docs": seed_docs}, fix_class="claude_md_link")`.

Edge case: a doc inside `docs/health/` is generated by Plugin B and intentionally excluded. Same for `docs/superpowers/**` (specs/plans separate domain).

#### `doc.broken_link`

For every doc in scope, for every `MarkdownLink`:
1. If `target` is absolute URL (`http://`, `https://`, `mailto:`) → skip.
2. If `target` starts with `#` (in-page anchor) → check anchor exists in current doc's `anchors`.
3. Else resolve `target` relative to current doc's directory:
   - If file part missing on disk → `doc.broken_link` (file).
   - If file exists but `#anchor` doesn't match `anchors_by_path[target]` → `doc.broken_link` (anchor).

For each broken link, check git-rename window: `git_renames.recent_renames(repo_root, since=rename_lookback)`. If the broken target is in the renames map → set `fix_class="doc_link_renamed"` and add `evidence["rename_to"] = renames[target]`. Otherwise `fix_class=None`.

Severity: WARN.

#### `doc.dead_code_ref`

1. Build symbol/path indices from `GraphSnapshot`:
   - `paths_in_graph: set[str]` — every `node["source_file"]` value.
   - `symbols_in_graph: set[str]` — every node id and every `node["label"].lower()`.
2. For every doc, for every `CodeRef`:
   - `kind="path_line"` or `kind="path"`: if `ref.path` not in `paths_in_graph` AND not on disk under `repo_root` → emit issue.
   - `kind="symbol"`: only flag if symbol contains `.` (qualified) AND `symbol.lower()` not in `symbols_in_graph`. Bare unqualified symbols (`config`, `engine`) are too noisy.
3. Severity: WARN. `evidence` includes `code_ref` text + source line.

#### `doc.stale_candidate`

1. For every doc:
   - `doc_iso = git_log.last_commit_iso(rel_path)` (skip if None — file uncommitted).
   - If `(today - doc_iso).days < stale_days` → skip.
2. For each `CodeRef` in the doc resolving to an existing src file:
   - `src_iso = git_log.last_commit_iso(src_rel_path)`.
   - If `src_iso > doc_iso` → emit `doc.stale_candidate` for the doc (one issue per stale doc, not per ref). Aggregate ref list in `evidence["changed_refs"]`.
3. Severity: INFO (per parent §5.3 — information only, no action).

#### `doc.adr_status_drift`

1. Find ADRs: `knowledge/adr/*.md` excluding `template.md`.
2. For each ADR, parse status:
   - YAML front matter `status` (case-insensitive) — accepted values: `accepted`.
   - Bold-line pattern `^\*\*Status:\*\*\s*Accepted\b` (case-insensitive).
3. If status is Accepted → run `dead_code_ref` logic on the ADR's content; emit issues with `rule="doc.adr_status_drift"` (separate id, higher visibility than generic `doc.dead_code_ref` for ADRs).
4. Severity: WARN.

ADRs are also scanned by the regular `dead_code_ref` rule (they live under `knowledge/`). To avoid double-reporting: `dead_code_ref` skips paths matching `knowledge/adr/*.md` when ADR drift is enabled.

#### `doc.coverage_gap`

1. For each name in `coverage_required`:
   - If `docs/<name>` does not exist → emit `doc.coverage_gap` (one issue per missing file).
2. Severity: WARN. `evidence["expected_path"] = f"docs/{name}"`.

### 4.6 Reuse from existing engine

| Component | Reused from |
|-----------|-------------|
| `IntegrityIssue`, `carry_first_seen` | `backend/app/integrity/issue.py` |
| `ScanContext`, `ScanResult`, `IntegrityPlugin` protocol | `backend/app/integrity/protocol.py` |
| `GraphSnapshot.load(repo_root)` | `backend/app/integrity/schema.py` |
| `git_renames.recent_renames` | `backend/app/integrity/plugins/graph_lint/git_renames.py` (no copy — direct import) |
| Engine, snapshots, report aggregator (report.json, report.md, docs/health/latest.md, trend.md append) | `backend/app/integrity/{engine,snapshots,report}.py` |
| `python -m backend.app.integrity` CLI | `backend/app/integrity/__main__.py` |
| Frontend Health page | already renders `docs/health/latest.md` raw — no changes needed |

## 5. Configuration

Append to `config/integrity.yaml`:

```yaml
plugins:
  doc_audit:
    enabled: true
    thresholds:
      stale_days: 90
    coverage_required:
      - dev-setup.md
      - testing.md
      - gotchas.md
      - skill-creation.md
      - log.md
    seed_docs:
      - CLAUDE.md
    doc_roots:
      - "docs/**/*.md"
      - "knowledge/**/*.md"
      - "*.md"
    excluded_paths:
      - "reference/**"
      - "node_modules/**"
      - "**/__pycache__/**"
      - "integrity-out/**"
      - "docs/health/**"
      - "docs/superpowers/**"
    claude_ignore_file: ".claude-ignore"
    rename_lookback: "30.days.ago"
    disabled_rules: []
```

Engine wiring (`backend/app/integrity/engine.py` or `wiring.py`): register `DocAuditPlugin` with config from `integrity.yaml`. Topological order remains A → B/C → ... (B and C depend on A, run after; B and C are independent of each other so engine may parallelize).

## 6. Data flow

```
nightly cron / manual / hook
        ↓
IntegrityEngine.discover()         (loads enabled plugins from config)
        ↓
topo run order: A → {B, C}         (B, C independent; both depend on A)
        ↓
DocAuditPlugin.scan(ctx)
  ├── Build MarkdownIndex once (parser/markdown.py)
  ├── Run each enabled rule (skip if in disabled_rules)
  └── Catch per-rule exceptions → IntegrityIssue(severity=ERROR)
        ↓
write integrity-out/{ISO-date}/doc_audit.json
        ↓
report.py aggregator (already shipped) merges A + B + C → report.json + report.md
        ↓
docs/health/latest.md updated (committed; same as gate β)
docs/health/trend.md appended (rolling 30 days)
        ↓
frontend Health page picks up new content (no code change)
```

## 7. CLI / Make targets

- New: `make integrity-doc` — runs `python -m backend.app.integrity --plugin doc_audit`. Acceptance gate target.
- Modified: `make integrity` — already topologically dispatches all enabled plugins; no change needed beyond registering Plugin C in the engine wiring.
- Modified Make help text for `integrity` to read `Run the full integrity pipeline (A→B→C)`.

`__main__.py` already supports `--plugin <name>` from gate β. No CLI surface change.

## 8. Error handling

Per parent §8 + Plugin B's pattern:
- Per-rule exception caught in `DocAuditPlugin.scan` → `IntegrityIssue(severity="ERROR")` + `failures.append(...)`. Other rules continue.
- Plugin-wide failure (markdown-it-py import error, malformed `integrity.yaml`) → engine catches at top level → plugin marked `failed`, siblings continue.
- Repo without `graphify/graph.json` (Plugin A never ran) → `dead_code_ref` and `adr_status_drift` skip gracefully (empty graph indices); other rules unaffected.
- Repo without git history (CI shallow clone) → `stale_candidate` and `broken_link → doc_link_renamed` downgrade fall back to "no rename info, no stale info" (rules emit no issues, log warning to `failures` list). Engine/aggregator unaffected.

## 9. Testing

Per parent §9 — no 80% rule, but every rule gets ≥1 positive + 1 negative fixture.

### 9.1 Synthetic `tiny_repo` fixture

Built once via `conftest.py`. Mirrors real repo shape minimally:

```
tiny_repo/
  CLAUDE.md                # links to docs/dev-setup.md, docs/testing.md, etc.
  README.md                # not a seed, but reachable from CLAUDE.md
  docs/
    dev-setup.md           # required (coverage), reachable
    testing.md             # required, reachable
    gotchas.md             # required, reachable
    skill-creation.md      # required, reachable
    log.md                 # required, reachable
    orphan.md              # NOT reachable → doc.unindexed
    ignored.md             # in .claude-ignore → no issue
    broken.md              # links to docs/gone.md → doc.broken_link
    renamed-target.md      # was docs/old.md (in fake `git log` mock) → doc.broken_link with fix_class
    dead-ref.md            # `backend/app/missing.py:42` + `Module.gone_func` → doc.dead_code_ref
    stale.md               # mtime 91 days ago, refs backend/app/foo.py changed today
    anchor-broken.md       # links to docs/dev-setup.md#nonexistent → doc.broken_link (anchor)
  knowledge/adr/
    001-real.md            # Accepted, refs live foo.py.do_thing → no issue
    002-drift.md           # Accepted, refs missing.py.gone_func → doc.adr_status_drift
    003-proposed.md        # Status: Proposed, refs gone code → no issue (only Accepted gates)
    template.md            # excluded by ADR rule
  backend/app/foo.py       # has do_thing → present in graph
  graphify/
    graph.json             # nodes: foo.py.do_thing, foo.py
    graph.augmented.json   # extra nodes
  .claude-ignore           # docs/ignored.md
```

`coverage_gap` test fixture variant: temp-rename `docs/log.md` → assert one issue.

### 9.2 Per-rule tests

| Test file | Cases |
|-----------|-------|
| `test_unindexed.py` | (+) `orphan.md` flagged. (–) `dev-setup.md` not flagged. (–) `ignored.md` not flagged. (–) `docs/health/**` not flagged (excluded). |
| `test_broken_link.py` | (+) `broken.md` → 1 issue, no fix_class. (+) `renamed-target.md` (with mocked `git_renames`) → 1 issue with `fix_class="doc_link_renamed"` and `evidence["rename_to"]`. (+) `anchor-broken.md` → 1 anchor issue. (–) Valid links not flagged. (–) Absolute URLs (`https://...`) not checked. |
| `test_dead_code_ref.py` | (+) `dead-ref.md` → 2 issues (path + symbol). (–) References to live code not flagged. (–) Bare unqualified `config` not flagged. (–) ADR paths excluded (handled by `adr_status_drift`). |
| `test_stale_candidate.py` | (+) `stale.md` → 1 issue with `evidence["changed_refs"]`. (–) Recent doc (mtime <90d) not flagged. (–) Old doc with no changed refs not flagged. |
| `test_adr_status_drift.py` | (+) `002-drift.md` (bold-line Accepted) → flagged. (+) Equivalent YAML front matter ADR → flagged. (–) `001-real.md` (Accepted, live refs) → not flagged. (–) `003-proposed.md` (not Accepted) → not flagged. (–) `template.md` excluded. |
| `test_coverage_gap.py` | (+) Removing `docs/log.md` → 1 issue. (–) Full set present → 0 issues. (+) Custom `coverage_required` config respected. |
| `test_parser_markdown.py` | Headings → slugs (lowercase, hyphens). Links extracted (relative + absolute + anchor). Front matter parsed. |
| `test_parser_code_refs.py` | `path:line`, `path`, `Module.func` extracted. Bare prose words not matched. Code-fenced blocks (` ``` `) skipped. |
| `test_parser_git_log.py` | Cached lookup. Non-existent path → None. Invalid git → None. |
| `test_parser_ignore.py` | Glob patterns match. Comments + blank lines skipped. Missing file → empty matcher. |
| `test_plugin_integration.py` | Full plugin scan → exact issue count + rule distribution against `tiny_repo`. Asserts `doc_audit.json` artifact written with `rules_run` and `failures`. |

### 9.3 Smoke against real repo

- Plugin runs against `claude-code-agent` in CI's `make integrity` step → exit 0, no exceptions.
- Manual gate verification:
  ```
  make integrity-doc
  cat integrity-out/$(date +%F)/doc_audit.json | jq '.rules_run, (.issues | length)'
  ```

## 10. Acceptance gate γ (per parent §7)

Pass condition (must hold for **7 consecutive nightly runs** to close gate γ):

1. ✅ `make integrity-doc` exits 0 on the real repo.
2. ✅ `100%` of `docs/**/*.md` reachable from `CLAUDE.md` (or explicitly listed in `.claude-ignore`). Concretely: `doc.unindexed` issue count == 0 after one round of CLAUDE.md updates / `.claude-ignore` additions.
3. ✅ `doc.broken_link` issue count == 0 on the real repo.
4. ✅ `doc.adr_status_drift` runs against all `knowledge/adr/*.md` (verified by `rules_run` containing `doc.adr_status_drift`).
5. ✅ `pytest backend/app/integrity/plugins/doc_audit/` green.
6. ✅ Plugin C results visible in `docs/health/latest.md` (renders via aggregator).

INFO-severity issues (`doc.stale_candidate`) do not block the gate.

## 11. Operational defaults

| Setting | Default | Where to change |
|---------|---------|-----------------|
| Stale threshold | 90 days | `config/integrity.yaml: plugins.doc_audit.thresholds.stale_days` |
| Reachability roots | `["CLAUDE.md"]` | `config/integrity.yaml: plugins.doc_audit.seed_docs` |
| Required coverage files | 5 (per parent §5.3) | `config/integrity.yaml: plugins.doc_audit.coverage_required` |
| Doc roots | docs/, knowledge/, repo-root *.md | `config/integrity.yaml: plugins.doc_audit.doc_roots` |
| Git rename lookback | 30 days | `config/integrity.yaml: plugins.doc_audit.rename_lookback` |
| Excluded paths | reference, node_modules, integrity-out, docs/health, docs/superpowers | `config/integrity.yaml: plugins.doc_audit.excluded_paths` |
| `.claude-ignore` location | repo root | `config/integrity.yaml: plugins.doc_audit.claude_ignore_file` |

## 12. Open knobs (deferred — record decisions when raised)

- **Multi-seed reachability**: should `README.md` be a seed alongside `CLAUDE.md`? Default: no (CLAUDE.md is THE index). Revisit if PR-side users want READMEs as a separate root.
- **Anchor case-sensitivity**: GitHub renders `## My Section` → `#my-section`. Plugin C matches lowercase. If a doc uses raw `<a name="MySection"></a>`, plugin won't index it. Acceptable today; revisit in C.1 if needed.
- **Symbol fuzziness**: should `dead_code_ref` match unqualified symbols (`do_thing` vs `foo.do_thing`)? Default: no — too noisy. Could be enabled per-doc via front matter in a future C.1.
- **Per-domain seed docs**: e.g., `frontend/src/CLAUDE.md` as a sub-root for frontend docs. Out of scope for γ; configurable later via `seed_docs` extension.

## 13. Dependencies

- New: `markdown-it-py >= 3.0` in `backend/pyproject.toml` `[project.optional-dependencies] dev`.
- Reused: `git_renames`, `GraphSnapshot`, `IntegrityIssue`, engine, report, snapshots — no new deps.
- Frontend: none.

## 14. Migration / rollout

1. Land Plugin C with `enabled: true` in `config/integrity.yaml`.
2. First `make integrity` after merge will report current state (likely several `doc.unindexed` and `doc.broken_link` from real-repo legacy state).
3. Author CLAUDE.md additions / `.claude-ignore` entries to bring `doc.unindexed` to 0.
4. Author broken-link fixes to bring `doc.broken_link` to 0.
5. Once gate criteria hold for 7 consecutive nightly runs → mark this spec `Status: shipped` and close gate γ in parent spec front matter.

## 15. Spec lifecycle

Per parent §10:
- This sub-spec is the source of truth for Plugin C.
- Edit in place; bump `last_revised`.
- On gate γ closure (7 green nightly runs): set `status: shipped` here.
- On deprecation: set `status: deprecated` with `replaced_by:` pointer; keep file.

## 16. References

- Parent: `docs/superpowers/specs/2026-04-16-integrity-system-design.md` (mega-spec, §5.3 / §7 / §8 / §9)
- Plugin A spec: `docs/superpowers/specs/2026-04-16-integrity-plugin-a-design.md` (gate α — provides graph)
- Plugin B spec: `docs/superpowers/specs/2026-04-17-integrity-plugin-b-design.md` (gate β — provides engine + aggregator)
- `markdown-it-py` docs: https://markdown-it-py.readthedocs.io/
- ADR shape today: `knowledge/adr/001-python-over-typescript.md` (bold-line Status pattern)
- Plugin B implementation reference: `backend/app/integrity/plugins/graph_lint/` (mirror this shape)
