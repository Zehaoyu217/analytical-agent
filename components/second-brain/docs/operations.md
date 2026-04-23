# Operations

## Basic Workflow

1. ingest
2. extract or compile
3. reindex and derive chunk manifests
4. search and reason with provenance
5. maintain
6. evaluate regressions

## Core Commands

### Ingest

```bash
sb ingest <path-or-url>
```

### Extract

```bash
sb extract <source_id>
sb extract <source_id> --live --small-model mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit --large-model mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit
```

### Reindex

```bash
sb reindex
sb reindex --with-vectors
```

What reindex now does:

- rebuilds source / claim / center indexes
- derives `chunk_manifest.json` for each source
- populates chunk-level search rows
- populates chunk embeddings when vectors are enabled

For PDF sources, reindex expects `_source.md` to already contain page markers such as `<!-- page: 7 -->`. The current PDF ingest path requests those markers directly from the converter.

## Inspect Provenance

Useful inspection commands:

```bash
sb search "attention regularization" --json
sb load chk_attention_001
```

What to expect from a healthy provenance path:

- chunk hits may come back directly from search
- center hits may carry chunk evidence rows
- chunk loads should include `source_id`, `section_title`, `page_start`, and `page_end`

### Maintain

```bash
sb maintain --json
sb maintain --digest
```

### Inspect

```bash
sb status
sb search "query"
sb load <id>
sb reason <start_id> <relation>
sb eval --suite corpus --fixtures-dir /path/to/fixtures
```

## Maintenance Notes

- if canonical markdown changes, expect to reindex
- digest and gardener should be validated end-to-end after schema changes
- retrieval regressions should be checked with tests, not by spot intuition only

## Troubleshooting

If live extraction or reconciliation is unexpectedly fake:

1. check whether `SB_FAKE_CLAIMS` or `SB_FAKE_RESOLUTION` is set
2. run with `--live` to force a real model path
3. verify at least one configured live model is actually available
4. for MLX-backed local jobs, confirm `mlx-lm` is installed in the active environment
5. if the model is downloading from Hugging Face, confirm `HF_HUB_DISABLE_XET=1` is in effect on this machine

If a larger MLX model never finishes downloading:

1. do not treat that as a `second-brain` schema bug; first-time model download reliability is below the app layer
2. confirm the process is not stuck in Hugging Face Xet transfer paths; `HF_HUB_DISABLE_XET=1` is the default mitigation here
3. clear stale `*.incomplete` blobs under `~/.cache/huggingface/hub/models--<repo>/blobs/` before retrying
4. try the smaller local target first to validate the runtime path before blaming the schema or tool prompts
5. record the exact repo id and any downloader error before changing the component code

If Ollama reports `model failed to load`:

1. do not treat that as a `second-brain` schema bug; it is an Ollama runtime failure
2. try the MLX local path first on Apple Silicon before spending time on Ollama-specific debugging
3. lower `SECOND_BRAIN_OLLAMA_NUM_CTX` below the default `8192` if the host is memory-constrained
4. record the exact model id and daemon error before changing the component code

If search is stale:

1. confirm canonical markdown exists
2. run `sb reindex`
3. check `.sb/kb.sqlite`, `.sb/graph.duckdb`, and `sources/*/chunk_manifest.json`
4. rerun focused tests

If search is missing provenance:

1. inspect `_source.md` and confirm the extracted body still contains headings or page markers
2. load the corresponding `chunk_manifest.json`
3. confirm chunk rows in the manifest still have `section_title` and page fields
4. rerun retrieval tests before blaming the broker or UI

If page spans are empty:

1. check whether the converter preserved any page boundaries at all
2. for PDFs, confirm `_source.md` contains `<!-- page: N -->` markers
3. do not assume retrieval is broken; missing page markers and broken retrieval are different problems
4. treat this as an extraction-quality issue unless chunk manifests lost page info that used to exist

If host integration is stale:

1. verify backend dependency path still points to the nested component
2. verify `SECOND_BRAIN_HOME`
3. verify backend route adapters still match component contracts
4. verify backend payloads still include chunk provenance fields

## Provider Routing

Current live-model routing inside the component:

 - `mlx/...` -> local Apple Silicon MLX runtime
- `ollama/...` -> local Ollama
- `openai/...`, `google/...`, `meta-llama/...`, and other provider-qualified remote ids -> OpenRouter
- `anthropic/...` -> OpenRouter when `OPENROUTER_API_KEY` is present, otherwise native Anthropic
- bare `claude-*` ids -> native Anthropic

That routing is shared across extractor, reconciler, and gardener code paths.

## Corpus Eval Fixtures

The `corpus` eval suite is the recommended operator path for validating real PDFs and books before trusting them in long-running research loops.

A useful manifest usually checks:

- minimum page markers preserved in `_source.md`
- minimum chunk count after reindex
- minimum fraction of chunks with page provenance
- that the compiled paper summary is narrative rather than structural
- one or more brokered search queries that should resolve back to the paper with chunk evidence
