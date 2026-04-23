# AGENTS

Operator contract for coding agents working inside `components/second-brain`.

## Purpose

`second-brain` is a standalone knowledge-engine component nested inside `claude-code-agent`.

Treat it as:

- a normal Python package
- a standalone CLI project
- a deterministic data pipeline
- a host-integrated subsystem of `claude-code-agent`

## Canonical Files

These are the primary source of truth:

- `src/second_brain/**`
- `pyproject.toml`
- `README.md`
- `docs/*.md`
- `tests/**`
- user KB markdown under `SECOND_BRAIN_HOME`, especially:
  - `sources/**/_source.md`
  - `claims/*.md`
  - `claims/resolutions/*.md`
  - `papers/*.md`
  - `projects/*.md`
  - `experiments/*.md`
  - `syntheses/*.md`
  - `digests/*.md`
  - `.sb/habits.yaml`

## Derived Files

These can be rebuilt and should not be hand-edited:

- `.sb/graph.duckdb`
- `.sb/kb.sqlite`
- `.sb/vectors.sqlite`
- `.sb/analytics.duckdb`
- `.sb/.state/pipeline.json`
- `sources/*/chunk_manifest.json`
- `views/obsidian/**`
- digest sidecars and audit logs unless the task is explicitly about those emitters

## Safe Commands

Run from `components/second-brain/` unless the task requires the host app:

```bash
pytest --ignore=tests/test_ingest_pdf.py
python -m second_brain.cli --help
sb status
sb compile-center
sb reindex
sb maintain --json
sb export-obsidian
sb eval --help
sb eval --suite corpus --fixtures-dir /path/to/fixtures
```

Host integration checks from `claude-code-agent/backend/`:

```bash
uv run pytest tests/tools/test_sb_tools.py tests/api/test_sb_api.py tests/api/test_sb_pipeline.py
```

Live LLM smoke checks when you are intentionally testing model paths:

```bash
sb extract <source_id> --live --small-model mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit --large-model mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit
sb reconcile --live --small-model mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit --large-model mlx/NexVeridian/gemma-4-26B-A4b-it-4bit
```

Useful env knobs:

- `OLLAMA_HOST`
- `SECOND_BRAIN_OLLAMA_NUM_CTX`
- `HF_HUB_DISABLE_XET`

## Required Rebuild Rule

If a task mutates canonical KB markdown or code that changes indexing semantics:

1. reindex the KB or run the relevant automated path
2. verify retrieval still works
3. prefer a focused regression test when possible

Examples:

- after `sb_promote_claim` behavior changes, verify the new claim becomes searchable
- after center-memory compiler changes, verify `papers/*.md` and brokered search stay aligned
- after chunking or reindex changes, verify `chunk_manifest.json` and provenance-bearing retrieval still line up
- after digest or gardener action schema changes, verify pending -> build -> apply still works
- after extractor changes, verify section titles and page spans did not silently degrade
- after backend search payload changes, verify direct hits and evidence hits still preserve chunk provenance fields
- after compiler summary changes, verify long PDFs and books do not collapse to table-of-contents text

## Mutation Safety

- do not edit derived DB files directly
- do not rely on `.claude/settings.json` hooks as the only correctness mechanism
- do not assume filenames are canonical ids
- do not silently weaken schema validation to make tests pass
- do not treat empty page spans as harmless when the task is about paper-grounded recall; check whether extraction lost page markers
- do not assume a local-model download path is healthy just because the repo id resolves; on this machine the Xet downloader needed to be disabled for larger MLX pulls
- if you intentionally use Ollama, do not assume an installed Ollama model is actually loadable; a `500 model failed to load` response is a runtime-capacity signal, not proof that routing is broken

## Provenance Expectations

When retrieval is working correctly:

- a source can produce chunk ids such as `chk_<slug>_001`
- `sb load <chunk_id>` should return `source_id`, `section_title`, `page_start`, and `page_end`
- `sb search` JSON output should preserve provenance on hits and evidence rows
- prompt injection should render section and page details when they exist

If any one of those layers drops provenance, treat it as a regression in research recall quality.

## Priority Order

1. lifecycle correctness
2. retrieval quality
3. provenance quality
4. maintenance correctness
5. cost and prompt efficiency

This component currently favors proof-of-concept runtime settings, but code quality should remain production-grade.
