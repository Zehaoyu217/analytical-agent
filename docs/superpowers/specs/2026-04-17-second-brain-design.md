# Second Brain — design spec

> Historical note (2026-04-22): This spec was written when `second-brain` lived
> at `~/Developer/second-brain/`. The active codebase has since been moved into
> `claude-code-agent/components/second-brain`. Path references in this document
> are historical unless explicitly updated.

**Date:** 2026-04-17
**Status:** Draft (awaiting implementation plan)
**Scope:** Standalone side-project that produces a curated, graph-backed knowledge base which claude-code-agent consumes via a skill, a small tool set, and a prompt-time injection hook.

## 0. One-paragraph summary

Second Brain is a personal knowledge base maintained by Claude (Opus 4.7) the way a codebase is maintained: files on disk, git-versioned, human-auditable, continuously linted. You drop PDFs, URLs, repos, and notes into `~/second-brain/inbox/`. The `sb` CLI ingests them into per-source folders (`raw/*` + `_source.md`), extracts atomic claims into `claims/*.md`, and rebuilds a property graph (DuckDB + DuckPGQ) plus a BM25 index (SQLite FTS5) from the markdown. Edges are typed (`cites`, `supports`, `contradicts`, `refines`, …) with confidence tags (`extracted`, `inferred`, `ambiguous`). A contradiction is a first-class edge — healthy until resolved, with a `resolution:` note — not a conflict to be silently collapsed. claude-code-agent reads from the KB via three tools (`sb_search`, `sb_load`, `sb_reason`) and receives top-k claim abstracts injected into its system prompt on every turn. A habits file (`habits.yaml`), captured by an interactive wizard and refined by a ≥3-override learning detector, encodes your taxonomy, naming, extraction density, and autonomy preferences.

## 1. Goals and non-goals

### Goals
- Persistent, portable, diffable knowledge base. Markdown is source of truth.
- Claude (Opus 4.7) maintains it: ingest, extract, lint, reconcile, compact.
- First-class graph reasoning: "walk the supports chain from X" is a one-call tool.
- First-class contradictions: disagreement is healthy; resolution is explicit.
- Near-zero-cost retrieval injection on every agent prompt (BM25 + abstracts).
- Personal: one user, one KB, captured habits drive behavior.
- Standalone: the KB is consumable by any Claude Code session, not just claude-code-agent.

### Non-goals (v1)
- Multi-user or shared KBs.
- Real-time collaboration.
- Hybrid retrieval (BM25 + embeddings + RRF) — extension point only.
- Automatic forgetting or memory decay.
- MCP server — upgrade path documented; not v1.

## 2. Two repos, clean boundary

- **`second-brain/`** — the tool. Python package, `sb` CLI, installable via `pip install second-brain`. Versioned like any project.
- **`~/second-brain/`** — the data. User content. Separately versioned in git. Derived indexes in `.sb/` (gitignored).

Conventions:
- Repo name: `second-brain`
- Python package: `second_brain`
- CLI binary: `sb`
- Data home: `~/second-brain/` (overridable via `SECOND_BRAIN_HOME`)
- Derived indexes: `~/second-brain/.sb/`

## 3. Repository layout

### `second-brain/` (the tool)

```
second-brain/
├── README.md
├── pyproject.toml
├── src/second_brain/
│   ├── cli.py                       # sb init | ingest | reindex | lint | watch | serve | reconcile | habits
│   ├── config.py                    # SECOND_BRAIN_HOME resolution
│   ├── habits.py                    # habits.yaml load/save/validate
│   ├── ingest/
│   │   ├── base.py                  # Converter protocol + IngestInput
│   │   ├── pdf.py                   # markitdown wrapper
│   │   ├── url.py                   # httpx + readability + playwright screenshot
│   │   ├── repo.py                  # gh repo clone + README/doc cherry-pick
│   │   ├── note.py                  # .md / .txt passthrough
│   │   ├── docx.py                  # markitdown
│   │   ├── epub.py                  # markitdown
│   │   └── orchestrator.py          # pick converter, allocate folder, write frontmatter, queue extraction
│   ├── extract/
│   │   ├── claims.py                # Opus 4.7 claim extractor (schema-constrained JSON)
│   │   └── worker.py                # async queue worker
│   ├── graph/
│   │   ├── schema.py                # DuckDB DDL + DuckPGQ property graph
│   │   ├── store.py                 # GraphStore protocol
│   │   └── reason.py                # sb_reason + typed GraphPattern
│   ├── index/
│   │   └── bm25.py                  # SQLite FTS5 Retriever
│   ├── analytics/
│   │   └── views.py                 # DuckDB analytical views
│   ├── lint/
│   │   ├── rules.py
│   │   └── runner.py
│   ├── reindex.py                   # deterministic: markdown → DuckDB + FTS5
│   ├── inject.py                    # `sb inject` for UserPromptSubmit hook
│   ├── wizard.py                    # `sb init` interactive flow
│   └── server/                      # OPTIONAL `sb serve` HTTP/MCP surface (deferred)
├── .claude/
│   ├── skills/                      # skills Claude loads when running IN second-brain/
│   │   ├── sb-ingest/
│   │   ├── sb-extract-claims/
│   │   ├── sb-reconcile/
│   │   ├── sb-lint/
│   │   └── sb-init/                 # the wizard skill
│   └── settings.json                # PostToolUse: on Write to _source.md → debounced reindex
├── tests/
└── docs/                            # architecture, schema, how-to-extend
```

### `~/second-brain/` (the data)

```
~/second-brain/
├── .sb/
│   ├── habits.yaml                  # captured by wizard, single source of config
│   ├── kb.sqlite                    # FTS5 index (derived, gitignored)
│   ├── graph.duckdb                 # DuckDB + DuckPGQ (derived, gitignored)
│   └── analytics.duckdb             # DuckDB analytical views (derived, gitignored)
├── sources/
│   └── <slug>/
│       ├── _source.md               # frontmatter + processed body
│       ├── raw_manifest.json        # authoritative list of raw/*
│       └── raw/
│           ├── paper.pdf            # or page.html + screenshot.png, etc.
│           └── …
├── claims/
│   ├── <slug>.md                    # one file per extracted claim
│   └── resolutions/
│       └── <slug>.md                # reconciliation notes for resolved contradictions
├── inbox/                           # drop zone for unstructured items
├── proposals/                       # habit-learning proposal diffs pending approval
├── index.md                         # auto-regenerated: sources by taxonomy, claim count
├── conflicts.md                     # auto-regenerated: open debates + healthy signal
└── log.md                           # append-only, structured event log
```

## 4. Schema (the public contract)

### 4.1 Source file — `sources/<slug>/_source.md`

```markdown
---
id: src_2017_attention-is-all-you-need
title: "Attention Is All You Need"
kind: pdf                          # pdf | url | repo | note | docx | epub | failed
authors: ["Vaswani, A.", "Shazeer, N."]
year: 2017
source_url: "https://arxiv.org/abs/1706.03762"
tags: [ml/transformers, architecture]
ingested_at: 2026-04-17T11:04:23Z
content_hash: sha256:9a8f…
habit_taxonomy: "papers/ml"
raw:
  - path: "raw/paper.pdf"
    kind: original
    sha256: "…"
  - path: "raw/screenshot.png"
    kind: screenshot
cites: [src_2015_layer-norm]       # source → source
related: [src_2014_seq2seq]
supersedes: []
abstract: |
  3-sentence Claude-written retrieval abstract, BM25-optimized.
  Regenerated only when content_hash changes.
---

# Attention Is All You Need

<markitdown-processed body, cleaned, section-structured>
```

### 4.2 Claim file — `claims/<slug>.md`

```markdown
---
id: clm_attention-replaces-recurrence
statement: "Self-attention alone, without recurrence or convolution, is sufficient for sequence transduction."
kind: empirical                    # empirical | theoretical | definitional | opinion | prediction
confidence: high                   # low | medium | high (Claude's read, user-editable)
scope: "sequence-to-sequence neural models"
supports:                          # claim → source
  - src_2017_attention-is-all-you-need#sec-3.2
contradicts:                       # claim → claim
  - clm_recurrence-is-essential-for-long-range-deps
refines:                           # claim → claim
  - clm_attention-helps-seq-transduction
extracted_at: 2026-04-17T11:06:11Z
status: active                     # active | superseded | retracted | disputed
resolution: null                   # path to claims/resolutions/<slug>.md if contradicting
abstract: |
  Short BM25-optimized summary of the claim + its key terms.
---

# Attention replaces recurrence

<optional Claude reasoning about scope, caveats, falsification>
```

### 4.3 Edge types and confidence

| Relation | Direction | Carries | Typical confidence source |
|---|---|---|---|
| `cites` | source → source | src_A quotes src_B | extracted (direct citation), inferred (Claude match) |
| `related` | source → source | soft link | inferred |
| `supersedes` | source → source | newer replaces older | extracted when author says so |
| `supports` | claim → source | claim grounded in evidence | extracted (quote), inferred |
| `evidenced_by` | claim → source | auto-derived reverse of `supports` | (derived) |
| `contradicts` | claim → claim | healthy disagreement | extracted (both quoted), inferred, ambiguous |
| `refines` | claim → claim | narrower version | inferred |

Every edge carries `confidence ∈ {extracted, inferred, ambiguous}`. Lint treats contradictions differently by confidence (Section 7).

### 4.4 Schema invariants

1. **Source of truth is markdown frontmatter.** DuckDB and FTS5 are rebuildable derivations.
2. **IDs are human-readable, prefixed, stable.** `src_*`, `clm_*`. Never change once written.
3. **Edges stored once, reverse materialized by reindex.** Lint warns on redundant both-sides declarations.
4. **Abstracts are content-hash-gated.** Regenerated only on content change.
5. **Never hand-write the graph DB.** All graph mutations flow through markdown edits.
6. **Contradictions require resolution to count as healthy.** Unresolved-after-grace-period is a lint warning; resolved-with-note is a positive health signal.

## 5. Ingest pipeline

### 5.1 Two entry points
- `sb ingest <path-or-url> [--kind auto] [--slug <slug>]` — explicit.
- `sb process-inbox` — batch over `~/second-brain/inbox/`.

### 5.2 Converter protocol (stream-based, no tmp files)

```python
class Converter(Protocol):
    kind: ClassVar[str]  # pdf | url | repo | note | docx | epub

    def matches(self, source: IngestInput) -> bool: ...

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        """
        source carries an open byte stream + origin metadata (never a tmp path).
        Writes raw/* directly, returns processed markdown body + raw_manifest.
        Does NOT write _source.md — orchestrator does that.
        """
```

### 5.3 v1 converters

| Converter | Handles | Library |
|---|---|---|
| `pdf.py` | `.pdf` | markitdown |
| `url.py` | `http[s]://…` | httpx + readability-lxml + playwright |
| `repo.py` | `gh:owner/repo` or local path | `gh repo clone --depth 1`, glob capture per habits |
| `note.py` | `.md` / `.txt` | pass-through with frontmatter injection |
| `docx.py`, `epub.py` | `.docx`, `.epub` | markitdown |

### 5.4 Orchestrator flow

```python
def ingest(source: IngestInput) -> SourceFolder:
    converter = pick_converter(source, habits.taxonomy_hints)
    slug = propose_slug(source, habits.naming_convention)                       # Claude-proposed
    target = SourceFolder.create(home() / "sources" / slug)
    artifacts = converter.convert(source, target)                               # writes raw/*
    frontmatter = build_frontmatter(source, artifacts, habits)                  # no `cites`/`related` yet
    target.write_source_md(frontmatter, artifacts.processed_body)
    extractor.enqueue(target, density=resolve_density(frontmatter.kind, habits))
    reindex.enqueue()                                                           # debounced
    return target
```

Notes:
- **Slug policy:** Claude-proposed, user-confirmable in interactive `sb ingest`; auto-committed in `sb process-inbox` batch mode.
- **Frontmatter at ingest time** fills: id, title, kind, content_hash, ingested_at, raw.*, tags (proposed), habit_taxonomy (proposed), abstract. Does **not** fill: cites, related, supersedes (deferred to `sb reconcile`).
- **Extraction is async.** Ingest returns in ~2s; claim extraction runs in a background worker.

### 5.5 Claim extraction (schema-constrained)

- Input: `processed_body`, `density`, `habits.extraction.claim_rubric`.
- Output: JSON array of claim records matching the claim frontmatter schema.
- Uses structured output via the Anthropic SDK (tool-use with `input_schema`) to constrain Opus 4.7 output — avoids the "unconstrained LLM extraction" noise pattern flagged by the lit review.
- Each claim + each edge tagged with `confidence ∈ {extracted, inferred, ambiguous}`.
- **Adaptive density resolution:** `by_kind` → `by_taxonomy` (most-specific prefix match) → `default_density`.

### 5.6 Error handling
- **Converter fails:** source created with `kind: failed`, raw file preserved, error in frontmatter, entry in `log.md`. Retry with `sb ingest --retry <slug>`.
- **Extraction fails:** 3-attempt exponential backoff. After 3 failures, `log.md` flags; `claims/` stays empty; `sb lint` surfaces as `SPARSE_SOURCE`.
- **Duplicate detection:** `content_hash` check before ingest. Exact dup aborts with existing `src_*` printed. Near-dup (v2, when embeddings arrive) via cosine > 0.85.

## 6. Graph layer (DuckDB + DuckPGQ)

### 6.1 Tables

```sql
CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  slug TEXT, title TEXT, kind TEXT,
  year INT, habit_taxonomy TEXT,
  content_hash TEXT, abstract TEXT,
  ingested_at TIMESTAMP
);

CREATE TABLE claims (
  id TEXT PRIMARY KEY,
  statement TEXT, body TEXT, abstract TEXT,
  kind TEXT, confidence_claim TEXT, status TEXT,
  resolution TEXT
);

CREATE TABLE edges (
  src_id TEXT, dst_id TEXT,
  relation TEXT,           -- cites | related | supersedes | supports | contradicts | refines | evidenced_by
  confidence_edge TEXT,    -- extracted | inferred | ambiguous
  rationale TEXT,
  source_markdown TEXT,    -- which .md declared this edge (traceability)
  PRIMARY KEY (src_id, dst_id, relation)
);
```

### 6.2 Property graph view (DuckPGQ)

```sql
CREATE PROPERTY GRAPH sb_graph
  VERTEX TABLES (sources, claims)
  EDGE TABLES (
    edges SOURCE KEY (src_id) REFERENCES sources(id)
                DESTINATION KEY (dst_id) REFERENCES sources(id)
          LABEL cites,
    -- analogous entries for related / supersedes / supports / contradicts / refines / evidenced_by
  );
```

### 6.3 Reindex guarantees
- **Deterministic.** Same markdown → byte-identical `kb.sqlite` + `graph.duckdb`.
- **Atomic.** Builds into `.sb/next/` then renames.
- **Fast.** Under 10s for 1000 sources / 3000 claims on SSD. Incremental reindex deferred to v2.
- **Debounced.** 5s coalescing window for rapid-fire triggers.
- **Triggers:** (a) ingest completion, (b) Write on any `_source.md`/`claims/*.md` via claude-code hook, (c) explicit `sb reindex`, (d) nightly `sb maintain`.

## 7. Lint and reconciliation

### 7.1 Rules by severity

**Error** (never blocks local work; blocks hypothetical `sb publish`):
- `ORPHAN_CLAIM` — no live `supports:` targets.
- `DANGLING_EDGE` — frontmatter references missing id.
- `CIRCULAR_SUPERSEDES` — cycle in supersedes chain.
- `HASH_MISMATCH` — recomputed `content_hash` differs from stored.

**Warning** (shown in `conflicts.md`):
- `UNRESOLVED_CONTRADICTION` — `contradicts` edge at `confidence: extracted`, no `resolution:`, older than `habits.conflicts.grace_period_days` (default 14).
- `LOPSIDED_CONTRADICTION` — claim with ≥3 contradictors and no outbound contradicts (likely widely-disputed, worth flagging).
- `STALE_ABSTRACT` — content changed but abstract not regenerated.
- `SPARSE_SOURCE` — source with 0 claims after 3 retries.

**Info** (healthy signal in `conflicts.md`):
- `HEALTHY_CONTRADICTION` — contradiction with a resolution note. Counted toward health score.
- `CONTRADICTION_CLUSTER` — ≥`habits.conflicts.cluster_threshold` (default 3) mutually-contradicting claims.

### 7.2 Confidence-aware contradiction triage

- `confidence: extracted` (both sources quoted) → **unresolved after grace → warning**
- `confidence: inferred` (Claude reasoned) → **candidate, needs confirm/reject** (dismiss via `rejected: true`)
- `confidence: ambiguous` → **low-priority review**

This avoids flooding `conflicts.md` with every nuance disagreement Opus detects between sources.

### 7.3 `conflicts.md` layout

Auto-regenerated every reindex. Sections:
1. **Open debates** (unresolved extracted contradictions past grace period).
2. **Candidate contradictions** (inferred, needs confirmation).
3. **Healthy signal** (resolved count, avg time to resolution, clusters).

### 7.4 Reconciliation flow — `sb reconcile`

Claude Code skill `sb-reconcile` that:
1. Reads top-N open debates.
2. Loads both claims + supporting sources.
3. Proposes a `claims/resolutions/<slug>.md` explaining the contradiction (scope difference, methodological difference, different eras, etc.).
4. Updates one side's frontmatter to point at the resolution.
5. In `hitl` mode: surfaces proposals for review. In `auto` mode: commits with reasoning logged to `log.md`.

## 8. Index and retrieval

### 8.1 SQLite FTS5

```sql
CREATE VIRTUAL TABLE claim_fts USING fts5(
  claim_id UNINDEXED, statement, abstract, body, taxonomy,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE source_fts USING fts5(
  source_id UNINDEXED, title, abstract, processed_body, taxonomy,
  tokenize = 'unicode61 remove_diacritics 2'
);
```

Field weights via `bm25()` column weights:
- Claims: `statement: 3.0, abstract: 2.0, body: 1.0`
- Sources: `title: 3.0, abstract: 2.0, processed_body: 1.0`

### 8.2 Retriever protocol

```python
class Retriever(Protocol):
    def search(
        self,
        query: str,
        k: int = 10,
        scope: Literal["claims", "sources", "both"] = "both",
        taxonomy: str | None = None,          # prefix match, e.g. "papers/ml/*"
        with_neighbors: bool = False,
    ) -> list[RetrievalHit]: ...

@dataclass(frozen=True)
class RetrievalHit:
    id: str
    kind: Literal["claim", "source"]
    score: float
    matched_field: str
    snippet: str
    neighbors: list[str]  # 1-hop neighbor IDs, if with_neighbors
```

### 8.3 Three retrieval operations

- **`sb_search(query, k, scope, taxonomy, with_neighbors)`** — BM25 retrieval. `with_neighbors=True` enriches each hit with 1-hop graph neighbor IDs (via DuckPGQ).
- **`sb_load(node_id, depth, relations)`** — graph-aware fetch. `depth=0` = just the node; `depth=1` = node + 1-hop full content + edge metadata; `depth=N` = subgraph, content for depth ≤ `habits.retrieval.max_depth_content` (default 1), ID+abstract beyond. `relations` filters edge types.
- **`sb_reason(start_id, pattern)`** — typed graph reasoning.

```python
@dataclass(frozen=True)
class GraphPattern:
    walk: str                         # relation name, e.g. "refines"
    direction: Literal["outbound", "inbound", "both"]
    max_depth: int
    terminator: str | None = None     # relation to stop on, e.g. "supersedes"
    filter: Filter | None = None      # confidence / status filters
```

Shorthand helpers:
- `sb_reason_chain(start, "supports")` — foundational-premise walk
- `sb_reason_contradictions(start, max_depth=2)` — adversarial subgraph
- `sb_reason_refinement_tree(start)` — refinement hierarchy

All compile to SQL/PGQ against DuckPGQ.

### 8.4 Prompt-time injection — `sb inject`

Wired as a `UserPromptSubmit` hook in claude-code-agent:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "command": "sb inject --k 5 --scope claims --max-tokens 800 --prompt-stdin" }
    ]
  }
}
```

`sb inject`:
1. Reads prompt from stdin.
2. BM25 with configured `k`, `scope`.
3. Emits a compact prefix block (claim ID + statement + edge summary), **never full bodies**.
4. Skip conditions: top score < `habits.injection.min_score` (0.2 default), or prompt matches `habits.injection.skip_patterns`.

Injection block format:

```
### Second Brain — top matches for this prompt

1. [clm_attention-replaces-recurrence] (score 0.87)
   Self-attention alone is sufficient for seq transduction.
   ◇ supports: src_2017_attention-is-all-you-need
   ◇ contradicts: clm_recurrence-is-essential-for-long-range-deps

Use sb_load(<id>, depth=1) to expand any of these.
```

### 8.5 Extension point for hybrid retrieval (deferred)

Keep `Retriever` as the interface. v2 can add `HybridRetriever` that fuses BM25 + embeddings via RRF (Reciprocal Rank Fusion, per QMD pattern) without breaking tool callers.

## 9. Maintenance operational model

### 9.1 Three modes (hybrid)

1. **User-driven (baseline).** `cd ~/second-brain && claude` opens a Claude Code session with the `sb-*` skills. You say "process inbox" / "reconcile contradictions" / "ingest this." Primary day-to-day flow.
2. **Watcher daemon (optional).** `sb watch` runs watchdog on `inbox/` + `raw/` drops, fires `claude -p --skill sb-ingest "<file>"` non-interactively. Drop-and-walk-away ergonomics. Concurrency guard on claim extraction via a single-worker queue.
3. **Scheduled maintenance.** `sb maintain` (cron/launchd, nightly 03:30 local by default): lint the full graph, flag new contradiction clusters, regenerate stale abstracts, compact indexes, run habit-learning detector (Section 10).

### 9.2 Coexistence with claude-code-agent's existing wiki

| | Wiki / `knowledge/wiki/` | Second Brain / `~/second-brain/` |
|---|---|---|
| Scope | Per-session operational state | Long-lived curated knowledge |
| Lifetime | Ephemeral (session notes pruned at 3 days) | Persistent |
| Source of truth | Claude's in-session thinking | External documents + extracted claims |
| Injection | `working.md` + `index.md` + session notes | BM25 claim abstracts |
| Graph | None | DuckPGQ property graph |
| Tools | `write_working`, `promote_finding`, `save_artifact` | `sb_search`, `sb_load`, `sb_reason`, `sb_ingest`, `sb_promote_claim` |

**Bridge tool: `sb_promote_claim(finding_id)`** — lifts a validated wiki finding into the KB as a `clm_*` node with `supports: [artifact_ids]`. This is the path for "today's finding becomes tomorrow's retrievable knowledge."

## 10. Habits and autonomy

### 10.1 `habits.yaml` schema (complete)

```yaml
identity:
  name: "Jay"
  primary_language: en

taxonomy:
  roots:
    - papers/ml
    - papers/systems
    - blog
    - news
    - notes/personal
    - notes/work
    - repos/ml
    - repos/infra
  enforce: soft                        # soft | strict

naming_convention:
  source_slug: "{kind-prefix}_{year?}_{title-kebab}"
  claim_slug: "{verb}-{subject-kebab}"
  max_slug_length: 80

extraction:
  default_density: moderate            # sparse | moderate | dense
  by_taxonomy:
    papers/*: dense
    blog/*: sparse
    news/*: sparse
    notes/*: moderate
    repos/*: sparse
  by_kind:
    url: sparse
  claim_rubric: |
    A claim is an atomic, falsifiable assertion. Skip rhetoric, background.
    Prefer author's exact phrasing. Tag `kind: opinion` when scope is limited.
  confidence_policy:
    require_quote_for_extracted: true
    max_inferred_per_source: 20

retrieval:
  prefer: claims                       # claims | sources | balanced
  default_k: 10
  default_scope: both
  max_depth_content: 1

injection:
  enabled: true
  k: 5
  max_tokens: 800
  min_score: 0.2
  skip_patterns:
    - "^/"
    - "^(git|gh|npm|pip|make)\\b"
    - "\\b(ssh|curl|docker)\\b"

conflicts:
  grace_period_days: 14
  cluster_threshold: 3

repo_capture:
  globs: ["README*", "docs/**/*.md", "pyproject.toml", "package.json", "Cargo.toml"]
  exclude_globs: ["node_modules/**", "target/**", ".git/**"]

autonomy:
  default: hitl                        # auto | hitl
  overrides:
    ingest.slug: auto
    ingest.taxonomy: hitl
    extraction.density_adjust: auto
    reconciliation.resolution: hitl
    reconciliation.reject_edge: auto
    habit_learning.apply: hitl

learning:
  enabled: true
  threshold_overrides: 3               # per user: ≥3 overrides in a dimension triggers suggest
  rolling_window_days: 90
  dimensions:
    - naming.source_slug
    - naming.claim_slug
    - taxonomy.roots
    - extraction.by_taxonomy
    - extraction.by_kind
    - injection.skip_patterns

maintenance:
  nightly:
    enabled: true
    time: "03:30"
    tasks: [lint, regen_abstracts_for_changed, rebuild_conflicts_md, prune_failed_ingests_older_than_30d, habit_learning_detector]
```

### 10.2 Autonomy model

- **`auto`** — Claude commits without prompting, logs decision + reasoning to `log.md` (structured entry, Section 10.4). User audits with `sb log --auto-decisions --since 7d`; reverts with `sb undo <log-entry-id>`.
- **`hitl`** — Claude proposes, pauses for approval. Approved or rejected decisions are logged.
- **Per-operation overrides** in `habits.yaml:autonomy.overrides` tune the default for specific ops. Defaults bias hitl for load-bearing judgments (taxonomy, resolutions) and auto for low-risk reversible ones (slug proposal, dismissing an inferred contradiction).

### 10.3 Habit learning

- **Detector runs nightly** during `sb maintain`.
- Scans `log.md` for `USER_OVERRIDE` entries within `learning.rolling_window_days`.
- **Triggers when ≥`learning.threshold_overrides` (default 3)** overrides accumulate in a learning dimension.
- Emits a proposed `habits.yaml` diff with:
  - Observed pattern
  - Proposed change
  - Sample override IDs for audit
- **`habit_learning.apply: hitl`** — diff written to `proposals/habits-<date>.md`; apply with `sb habits apply <file>` or `--reject`.
- **`habit_learning.apply: auto`** — applied immediately, revert window 7 days via `sb habits revert`.

### 10.4 Structured `log.md` entries

```
- 2026-04-17T14:22:11 [AUTO] ingest.taxonomy src_2026_attention-primer → papers/ml
  reason: {matches_neighbor: src_2017_attention-is-all-you-need, by_kind_default: null}
- 2026-04-17T14:25:03 [USER_OVERRIDE] ingest.taxonomy src_2026_attention-primer → papers/ml/transformers
  prior: papers/ml
- 2026-04-17T14:25:45 [SUGGEST] taxonomy.roots +papers/ml/transformers
  reason: 4 overrides in last 60 days added this sub-slot
```

Semi-structured: human-readable, regex-parseable by the learning detector.

## 11. Wizard (`sb init`)

Interactive Claude Code session driven by the `sb-init` skill. 5–10 minute interview. Asks in order:

1. **Identity + primary language.**
2. **What kinds of things you save** (derives `taxonomy.roots` from conversation, not form).
3. **Naming conventions** (Claude proposes `{kind}_{year?}_{title-kebab}`, shows concrete examples).
4. **Extraction density calibration** (Claude shows a sample paragraph, asks which claims you'd capture → seeds `claim_rubric`).
5. **Contradiction tolerance** (keep one, keep both with resolution, flag for later → `conflicts` defaults).
6. **Injection style** (top-k abstracts / top-k with neighbors / off by default).
7. **Maintenance schedule.**
8. **Review rendered `habits.yaml`, final edits.**

After wizard:
- Scaffolds `~/second-brain/` tree
- Writes `habits.yaml`
- Creates empty `inbox/`
- Writes starter `README.md` describing layout
- Runs `sb reindex` to create empty `kb.sqlite` + `graph.duckdb`
- Prints claude-code-agent hook wiring instructions

Re-entry:
- `sb init --reconfigure` — habits only, no directory changes
- `sb habits edit` — `$EDITOR` direct edit
- `sb habits validate` — schema-validate (used as pre-flight for every `sb` command)

## 12. Consumer integration (claude-code-agent side)

### 12.1 Three artifacts added to claude-code-agent

1. **Skill:** `backend/app/skills/second_brain/SKILL.md` (Level-1, Reference-type, <200 lines). Sub-skills: `second_brain/schema.md`, `second_brain/reasoning-patterns.md`.
2. **Tools** registered in `chat_api.py`:

   | Tool | Purpose |
   |---|---|
   | `sb_search` | BM25 retrieval |
   | `sb_load` | Graph-aware fetch with depth |
   | `sb_reason` | Typed graph reasoning |
   | `sb_ingest` | Push into KB mid-conversation |
   | `sb_promote_claim` | Bridge wiki finding → KB claim |

   Implementation: direct Python calls into `second_brain` package (added as dep). No new process.
3. **Hooks** in `claude-code-agent/.claude/settings.json`:

   ```json
   {
     "hooks": {
       "UserPromptSubmit": [
         { "command": "sb inject --k 5 --scope claims --max-tokens 800 --prompt-stdin" }
       ],
       "PostToolUse": [
         {
           "matcher": "sb_ingest|sb_promote_claim",
           "command": "sb reindex --debounced"
         }
       ]
     }
   }
   ```

### 12.2 Config + graceful degradation

`backend/app/config.py`:

```python
SECOND_BRAIN_HOME: Path = Path(os.environ.get("SECOND_BRAIN_HOME", "~/second-brain")).expanduser()
SECOND_BRAIN_ENABLED: bool = SECOND_BRAIN_HOME.exists() and (SECOND_BRAIN_HOME / ".sb").exists()
```

If `.sb/` missing, tools and hook silently no-op. Agent remains usable without the KB.

### 12.3 MCP upgrade path (deferred)

`sb serve` would start an MCP server exposing the same primitives. Tool interfaces in claude-code-agent stay identical; routing flips from library call to MCP client. Filesystem contract in Section 4 is the stable boundary.

## 13. Testing and observability

### 13.1 Test layers
- **Unit** (pytest, 80%+ coverage): converters against fixtures; slug proposer against title bank; lint rules on in-memory KBs; retrieval on deterministic FTS5 corpus; graph reasoning on DuckPGQ fixtures.
- **Integration:** end-to-end ingest with `vcr.py`-recorded Opus responses; reindex byte-identity vs golden; hook round-trip.
- **Eval (`sb eval`):**
  1. **Ingest quality** — 20 curated sources; golden `processed.md`; claim count within ±20% of target; BM25 recall@5 ≥ 0.8 on key terms.
  2. **Retrieval** — 30 query/answer pairs over seed KB (~100 sources, ~300 claims); nDCG@10 vs golden; p95 < 100ms; injection ≤ `max_tokens`.
  3. **Graph reasoning** — 10 curated queries with known structural answers; exact set match.

### 13.2 Observability
- `log.md` — primary event trail, semi-structured (Section 10.4).
- `sb status` — KB size, index freshness, open contradictions, inbox depth, queue depth.
- `sb stats --json` — machine-readable metrics.
- **Health score (0–100):** weighted sum of (sources-with-zero-claims, orphan claims, unresolved-past-grace contradictions, resolved/open contradiction ratio as positive signal, auto-decisions reverted within 7d).

### 13.3 Performance targets

| Operation | Target | Regression threshold |
|---|---|---|
| `sb ingest` single PDF (excl extraction) | < 3s | > 5s |
| Claim extraction per source | < 30s | > 90s |
| `sb reindex` 1000 sources / 3000 claims | < 10s | > 30s |
| `sb_search` | p95 < 100ms | > 300ms |
| `sb_reason` 3-hop traversal | p95 < 200ms | > 500ms |
| `sb inject` | p95 < 150ms | > 400ms |
| Nightly `sb maintain` | < 2min / 10k claims | > 5min |

## 14. Prior art and attribution

### Borrowed

| Pattern | Source | Where in this design |
|---|---|---|
| Confidence-tagged edges (`extracted \| inferred \| ambiguous`) | [Graphify](https://github.com/safishamsi/graphify) (28.4k⭐) | §4.3, §5.5, §7.2 |
| Content-hash extraction cache | Graphify | §4.1, §5.4 |
| Three-pass extraction (deterministic → LLM → confidence) | Graphify | §5.5 |
| Stream-based file conversion | [MarkItDown](https://github.com/microsoft/markitdown) (Microsoft) | §5.2 |
| SQLite FTS5 as retrieval backbone | [QMD](https://github.com/tobi/qmd) | §8.1 |
| RRF hybrid retrieval extension point | QMD | §8.5 |
| YAML frontmatter as universal metadata | Obsidian / Logseq / Dendron convergence | §4.1, §4.2 |
| Explicit contradiction audit trail (no silent overwrite) | [Supermemory](https://github.com/supermemoryai/supermemory) (critique) | §4.2, §7 |
| Schema-constrained claim extraction | LangChain + Kuzu pattern | §5.5 |
| DuckPGQ property graphs via SQL/PGQ | DuckDB ecosystem | §6 |

### Avoided

- Silent contradiction resolution (Supermemory's auto-forget pattern).
- Tool-specific link syntax (Logseq `title::`, Obsidian property panels).
- Unconstrained LLM graph extraction.
- Manual metadata entry as a precondition (QMD).
- Autonomous acceptance of ML-derived relations (Canary/oAMF: 72–85% accuracy is below the bar).

### Upgraded

- **Claim + Source hybrid node model** — closer to how Zettelkasten + Obsidian power-users structure vaults; the only model where contradiction edges are tractable.
- **Confidence-tiered lint** — missing middle between "accept all" (Graphify) and "confirm all" (Supermemory).
- **Habit learning from override patterns** — none of the reviewed tools learn from user corrections; v1 includes the ≥3-override detector.

## 15. Implementation sequencing (preview for the plan)

The spec covers all v1 subsystems. Rough ordering when the implementation plan is written:

1. Repo scaffold, `pyproject.toml`, CLI skeleton.
2. Schema + `reindex` (markdown → empty DuckDB + FTS5). Tested with hand-written fixture sources/claims.
3. Converter protocol + `pdf.py` + `note.py` (simplest handlers).
4. Orchestrator + claim extraction worker + structured Opus output.
5. Remaining converters: `url.py`, `repo.py`, `docx.py`, `epub.py`.
6. Lint rules + `conflicts.md` generator.
7. Retriever (`sb_search`) + `sb_load` + `sb_reason` (with DuckPGQ).
8. `sb inject` + claude-code-agent hook wiring + `second_brain` skill + tool registrations.
9. Wizard (`sb init`) + `habits.yaml` schema + per-operation autonomy.
10. Habit learning detector + auto/hitl apply.
11. Maintenance (`sb maintain`, `sb watch`).
12. Eval suite, performance budgets, health score.

## 16. Open questions / deferred to plan

- **Near-dup detection before embeddings arrive** — spec currently uses BM25 top-20 term overlap; good enough?
- **Multi-home support** — if you ever want `~/second-brain-work/` and `~/second-brain-personal/`, is that v2 or never?
- **Claim promotion across sources** — when a new claim extracted from source B duplicates one from source A, do we merge (add `supports: [A, B]`) or create a separate claim with `refines:` edge? Spec default: merge if statement similarity is high; plan should pin the threshold.
- **Reconciliation cost** — Opus reconciling 50 open debates nightly could be expensive. Plan should budget token cost and set a cap.

---

## Appendix A — Glossary

- **Source** — an ingested artifact (PDF, URL, repo, note). One folder in `sources/`.
- **Claim** — an atomic, falsifiable assertion extracted from a source. One file in `claims/`.
- **Edge** — a typed, confidence-tagged relation between two nodes.
- **Contradiction** — an edge of type `contradicts` between two claims. Healthy if it carries a `resolution:` note.
- **Resolution** — a note at `claims/resolutions/<slug>.md` explaining *why* two claims contradict (scope, methodology, era, etc.) and which one applies where.
- **Habit** — an entry in `habits.yaml`. Drives naming, taxonomy, extraction, injection, autonomy, learning.
- **Reindex** — deterministic markdown → DuckDB + FTS5 rebuild.
- **Injection** — the `sb inject` hook that prefixes the system prompt with top-k claim abstracts.
- **hitl / auto** — autonomy modes. hitl = Claude proposes + waits. auto = Claude commits + logs + reversible.
