# Architecture

`second-brain` is the knowledge engine nested inside `claude-code-agent`.

## Current Shape

The current implementation is source-first, claim-first, and center-memory aware:

- ingest raw sources into `sources/`
- extract claims into `claims/`
- derive chunk manifests per source
- compile paper cards into `papers/`
- record project, experiment, and synthesis docs into typed center directories
- rebuild graph and search indexes into `.sb/`
- broker retrieval across center docs plus side-memory evidence
- expose retrieval, reasoning, digest, gardener, maintenance, and export workflows through the CLI and host app

The canonical contract is:

- markdown is the source of truth
- graph and search databases are derived

The retrieval contract is:

- center docs are what the agent should think with first
- chunks, claims, and whole sources are evidence layers
- the broker links evidence back into center docs when possible
- when no strong center object exists, side-memory hits are still returned directly with provenance

## Runtime Layers

### Canonical Layer

- `sources/<slug>/_source.md`
- `sources/<slug>/raw/*`
- `claims/*.md`
- `claims/resolutions/*.md`
- `papers/*.md`
- `projects/*.md`
- `experiments/*.md`
- `syntheses/*.md`
- `digests/*.md`
- `.sb/habits.yaml`

### Derived Layer

- `.sb/graph.duckdb`
- `.sb/kb.sqlite`
- `.sb/vectors.sqlite`
- `.sb/analytics.duckdb`
- `.sb/.state/*`
- `sources/*/chunk_manifest.json`
- `views/obsidian/*`

`chunk_manifest.json` is the main side-memory bridge artifact for source text. It contains deterministic chunk rows with:

- `id`
- `source_id`
- `ordinal`
- `section_title`
- `text`
- `start_char`
- `end_char`
- `page_start`
- `page_end`
- derived `page_span`

Those chunk rows are then indexed into:

- DuckDB `chunks`
- SQLite FTS `chunk_fts`
- optional vector store `chunk_vecs`

## Implemented Runtime Flow

1. sources are ingested into `sources/`
2. claims are extracted or promoted into `claims/`
3. `reindex` derives `chunk_manifest.json` and indexes chunk-level evidence
4. `compile-center` materializes bounded paper cards from source + claim state
5. `projects/`, `experiments/`, and `syntheses/` are written as typed center docs
6. `reindex` indexes sources, chunks, claims, and center nodes into DuckDB + FTS
7. the broker recalls center docs with linked chunk / claim / source evidence
8. `sb inject` and backend `sb_search` both use that brokered path
9. `export-obsidian` projects graph-worthy center docs into an Obsidian-friendly view

## Retrieval And Provenance Flow

1. `sb reindex` reads canonical source markdown.
2. `build_chunks(...)` segments each source into deterministic chunk records.
3. chunk records are written to `sources/<slug>/chunk_manifest.json`.
4. chunk rows are inserted into DuckDB and FTS, and optionally embedded.
5. `make_retriever(...)` can now return `claim`, `source`, or `chunk` hits.
6. the broker merges direct center hits with side hits and project-aware boosts.
7. broker evidence retains `source_id`, `chunk_id`, `section_title`, `page_start`, and `page_end`.
8. prompt injection and backend tool responses render those fields back to the agent or UI.

For PDF sources, this now depends on an explicit ingest-time contract: the PDF converter requests markdown page separators from `opendataloader_pdf` using `<!-- page: %page-number% -->`. That is the preferred path because it keeps page provenance attached to the extracted markdown instead of inventing it later in retrieval.

In practice, the most useful research path is:

- paper card or project doc as the primary recalled object
- chunk hits as the citation-like evidence behind that object

That keeps the center bounded while still exposing the raw literature trail.

## Host Relationship

Inside `claude-code-agent`, the backend imports the `second_brain` package directly and wraps it through:

- tool handlers
- REST adapters
- prompt injection wiring

The component remains independently testable and operable via `sb`.

## Important Current Limitation

Page provenance is inference-based, not guaranteed. The chunker can infer spans from:

- markdown page comments such as `<!-- page: 7 -->`
- simple page-marker lines such as `[page 7]`
- form-feed boundaries

If the PDF or URL extraction stage still drops page boundaries, chunk retrieval works, but page spans will be empty or approximate. The current PDF path is better than before because it explicitly requests page markers, but exact citation quality still depends on what the underlying converter can preserve.

## Target Direction

The long-term architecture in the host repo’s implementation plan expands this into:

- bounded center memory
- large side memory
- a broker that connects the two
- experiment write-back alongside literature memory
- an optional Obsidian-compatible projection for graph review and visualization

This component owns that evolution.

See [Obsidian Visualization](obsidian-visualization.md) for the projection-layer design.
