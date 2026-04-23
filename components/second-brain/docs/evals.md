# Evals

`second-brain` should be validated as both:

- a standalone component
- an embedded subsystem inside `claude-code-agent`

## Standalone Tests

Run from this component directory:

```bash
pytest --ignore=tests/test_ingest_pdf.py
```

Focused suites:

- retrieval tests
- chunker and provenance tests
- reindex tests
- ingest tests
- LLM provider-routing and tool-call tests
- digest tests
- gardener tests
- maintain tests
- corpus evals for real PDFs and books

## Host Integration Tests

Run from `claude-code-agent/backend/`:

```bash
uv run pytest tests/tools/test_sb_tools.py tests/api/test_sb_api.py tests/api/test_sb_pipeline.py tests/api/test_sb_gardener.py
```

## E2E Direction

The implementation plan in the host repo defines a canonical full-cycle E2E:

- ingest
- derive chunk manifests and evidence indexes
- compile or extract
- index
- retrieve
- write back experiment memory
- run digest and maintain
- verify host UI truthfulness

That lifecycle test should grow over time and remain deterministic.

## Corpus Suite

`sb eval --suite corpus --fixtures-dir <dir>` runs a hermetic document-corpus validation flow.

The suite accepts `fixtures_dir/corpus/manifest.yaml` with cases that point to either:

- local files via `source: ./inputs/paper.pdf`
- remote documents via `source: {url: https://..., filename: paper.pdf}`

For each case it runs:

1. ingest into a temp KB home
2. `compile-center`
3. `reindex`
4. structural checks on page markers, chunk counts, and pageful chunk ratio
5. center-summary quality checks
6. brokered retrieval assertions for one or more research queries

This is the preferred validation path for academic PDFs because it exercises the actual converter, chunker, center compiler, and retrieval broker together.

## Minimum Provenance Regression Pack

Every retrieval-quality change should re-verify at least this path:

1. ingest a fixture source with headings and explicit page markers
2. run `sb compile-center` and `sb reindex`
3. assert `sources/<slug>/chunk_manifest.json` exists and contains stable chunk ids
4. assert DuckDB load for a chunk id returns `source_id`, `section_title`, `page_start`, and `page_end`
5. assert FTS or hybrid retrieval can return a chunk hit for a paper-specific query
6. assert broker search can attach that chunk as evidence to a center doc
7. assert backend `sb_search` preserves the same provenance fields
8. assert prompt injection renders the evidence details without dropping them

## What To Treat As A Failure

These are real regressions, not cosmetic differences:

- chunk manifests disappearing after reindex
- chunk ids changing nondeterministically for the same source body
- section titles dropping after extractor or chunker changes
- page spans disappearing for fixtures that still preserve page markers
- backend adapters omitting provenance fields that the component emitted
- broker evidence collapsing back to whole-source snippets when chunk hits exist
- paper summaries degrading into page markers, headings, or table-of-contents lines
- live-model routing silently changing providers or model ids without an explicit config change
