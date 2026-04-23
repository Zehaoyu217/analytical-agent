# second-brain

Knowledge engine for long-running agent work. Markdown-as-truth, graph-backed, continuously maintainable.

This component lives inside `claude-code-agent` under `components/second-brain`, but it is structured to remain a self-contained project:

- standalone Python package: `second_brain`
- standalone CLI: `sb`
- standalone tests and evals
- standalone docs and operator guide
- explicit host integration contract for `claude-code-agent`

## What It Is

`second-brain` is the knowledge substrate behind the knowledge surfaces and `sb_*` tools in `claude-code-agent`.

Its job is to:

- ingest sources such as notes, PDFs, URLs, and repos
- compile durable center-memory knowledge objects from those sources
- index them for search and graph reasoning
- support brokered prompt-time and tool-time recall
- maintain the corpus through digest, gardener, and maintenance passes

Current implementation now includes a first center-memory slice:

- `papers/` compiled from `sources/` and linked claims
- `projects/`, `experiments/`, and `syntheses/` as typed center docs
- brokered recall that combines center memory with side-memory evidence
- `chunk_manifest.json` generated per source during reindex
- chunk-level indexing and retrieval with section + page-span provenance when inferable
- an Obsidian export view under `views/obsidian/`

That means the retrieval stack no longer operates only at whole-source granularity. During `sb reindex` each source body is segmented into deterministic chunk records, each chunk gets:

- a stable chunk id such as `chk_attention_001`
- a section title when one can be inferred from markdown headings
- a page span when the extracted text preserved page markers or boundaries
- DuckDB, FTS, and optional vector entries

The broker then uses those chunk hits as evidence for center-memory recall or returns them directly when no stronger center object exists.

For PDFs specifically, the ingest path now asks `opendataloader_pdf` to emit explicit markdown page separators in the form `<!-- page: N -->`. That gives reindex and chunking a stable page-boundary signal instead of relying on accidental markers in extracted text.

The longer-term architecture work in `claude-code-agent/knowledge_architecture_implementation_plan.md` continues from this base.

For the current delivered state of the component, including the MLX migration,
center-memory slice, provenance pipeline, and real-document validation, see
[Status](docs/status.md).

## Repository Layout

```text
components/second-brain/
  README.md
  AGENTS.md
  pyproject.toml
  src/second_brain/
  tests/
  docs/
    architecture.md
    data-model.md
    integration.md
    operations.md
    automation.md
    evals.md
  ops/
```

## Install

From this component directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
# optional vectors + local embedding stack
pip install -e '.[dev,vectors]'
sb --help
```

## Data Home

Data lives at `~/second-brain/` by default and can be overridden with `SECOND_BRAIN_HOME`.

```text
~/second-brain/
  .sb/
    habits.yaml
    graph.duckdb
    kb.sqlite
    vectors.sqlite
    analytics.duckdb
    .state/
  sources/
    <slug>/chunk_manifest.json
  claims/
    resolutions/
  papers/
  projects/
  experiments/
  syntheses/
  views/
    obsidian/
  digests/
  inbox/
  log.md
```

`chunk_manifest.json` is a derived artifact. It is rebuilt from `_source.md` during reindex and should not be edited by hand.

## Core Commands

### Setup

- `sb init [--defaults] [--reconfigure]`
- `sb status`

### Ingest And Compile

- `sb ingest <path|url>`
- `sb extract <source_id> [--density sparse|moderate|dense] [--model ...]`
- `sb compile-center`
- `sb reindex [--with-vectors]`

### Retrieve And Reason

- `sb search <query> [--k 10] [--scope claims|sources|both]`
- `sb search <query> --json`
- `sb load <id> [--depth 1]`
- `sb reason <start_id> <relation> [--depth 2]`
- `sb inject --prompt "..."` or `--prompt-stdin`

### Center Memory And Views

- `sb record-project <title> [--question ...]`
- `sb record-experiment <title> [--project-id ...] [--paper-id ...] [--claim-id ...]`
- `sb record-synthesis <title> [--project-id ...]`
- `sb export-obsidian`

### Maintain

- `sb lint [--write-conflicts]`
- `sb maintain [--json]`
- `sb maintain --digest`
- `sb digest build`
- `sb digest apply`
- `sb digest skip`
- `sb digest read`
- `sb eval`
- `sb eval --suite corpus --fixtures-dir <dir>`

## LLM Runtime Defaults

Heavy LLM paths inside `second-brain` now use provider-aware routing instead of Anthropic-only wiring:

- smaller live extraction requests default to `mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit`
- larger live extraction requests default to `mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit`
- reconciliation escalates further to `mlx/NexVeridian/gemma-4-26B-A4b-it-4bit` for deeper passes
- gardener defaults follow the same local split:
  - `cheap` -> `mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit`
  - `default` -> `mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit`
  - `deep` -> `mlx/NexVeridian/gemma-4-26B-A4b-it-4bit`
- `ollama/...` and remote provider ids still work, but they are no longer the default runtime for this repo

Operator overrides:

- `sb extract ... --model <id>`
- `sb extract ... --small-model <id> --large-model <id> --large-input-chars <n>`
- `sb reconcile ... --model <id>`
- `sb reconcile ... --small-model <id> --large-model <id> --large-input-chars <n>`

Apple Silicon setup note:

- install with the MLX extra: `uv sync --project components/second-brain --extra mlx`
- the backend extra now pulls `second-brain[mlx]`, so `uv sync --project backend --extra second-brain` installs the same local runtime
- `HF_HUB_DISABLE_XET=1` is set by default inside the MLX loader because Xet-backed downloads were unreliable on this machine for larger MLX models
- text-safe Gemma 4 MLX repos are preferred over generic multimodal MLX conversions for backend and maintenance work in this repo

## Documentation

- [Architecture](docs/architecture.md)
- [Status](docs/status.md)
- [Data Model](docs/data-model.md)
- [Integration](docs/integration.md)
- [Operations](docs/operations.md)
- [Automation](docs/automation.md)
- [Evals](docs/evals.md)
- [Obsidian Visualization](docs/obsidian-visualization.md)
- [Agent Operator Guide](AGENTS.md)

## Host Integration

`claude-code-agent` integrates this component through:

- backend imports of the `second_brain` Python package
- REST adapters under `backend/app/api/sb_*.py`
- tool handlers under `backend/app/tools/sb_*.py`
- prompt-time knowledge injection
- `.claude/settings.json` hooks for `sb inject` and `sb reindex`
- backend tool handlers that now auto-refresh center docs and indexes after ingest / claim promotion
- backend search results now surface evidence provenance fields such as `source_id`, `chunk_id`, `section_title`, and page spans

Important host-level behavior:

- prompt injection and backend `sb_search` now use the same brokered recall path
- `sb_load` can load chunk ids from the derived graph store
- direct search hits and evidence hits both carry provenance fields when the underlying source text preserved them

Page spans are only as good as the source extraction. If a converter strips page markers entirely, retrieval still works, but chunk hits will not have reliable page metadata.

The backend package dependency is wired through a local source path, so the nested component can be developed in-place without relying on a sibling checkout.

See [docs/integration.md](docs/integration.md) for details.

## Claude Code And Codex

This component is intended to be maintainable by coding agents as helpers, not only by humans.

Use [AGENTS.md](AGENTS.md) as the operating contract for:

- safe maintenance commands
- canonical vs derived files
- reindex expectations after mutations
- digest and gardener workflows
- eval and regression checks

For real-paper validation, the `corpus` eval suite can download or read local PDFs, run ingest -> compile-center -> reindex in a hermetic temp KB, and score:

- page-marker preservation
- chunk count and pageful chunk ratio
- center-summary quality
- brokered retrieval against expected research queries

## Tests

From this component directory:

```bash
pytest --ignore=tests/test_ingest_pdf.py
```

Coverage target remains `>= 75%`.
