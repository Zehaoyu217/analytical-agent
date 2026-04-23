# Status

This document records the major implementation work that has been completed for
`components/second-brain` inside `claude-code-agent`.

It is intentionally practical: what changed, what is running now, what was
validated, and what still remains open.

## Current State

`second-brain` is no longer just an external dependency assumption. It now
exists as a nested, self-contained component with:

- its own package, CLI, tests, and docs
- an explicit host integration contract
- a bounded center-memory layer
- provenance-bearing side-memory retrieval
- local Apple Silicon MLX support for heavy LLM workflows

The component is now suitable as the knowledge subsystem for long-running agent
research workflows where literature, experiments, and synthesis need to stay
connected over time.

## Major Work Completed

### 1. Nested Componentization

`second-brain` was moved into `claude-code-agent` as a first-class nested
component under `components/second-brain`.

That work included:

- standalone component docs and operator guidance
- local editable dependency wiring from the host backend
- a stable component directory layout for future independent evolution

### 2. Center Memory

The component now has a typed center-memory layer instead of operating only as a
source-plus-claims store.

Implemented center objects:

- `papers/`
- `projects/`
- `experiments/`
- `syntheses/`

These are compiled or recorded as bounded docs that the agent should think with
first, rather than forcing every retrieval path to operate directly on raw
source chunks.

### 3. Brokered Retrieval

Retrieval now operates through a broker that combines:

- center-memory hits
- claims
- source-level hits
- chunk-level evidence

This matters because the component can now return a useful paper or project doc
as the primary object while still attaching chunk-backed evidence and provenance
under it.

### 4. Chunk-Level Provenance

Reindex now derives `chunk_manifest.json` per source and indexes chunk-level
records into the graph/search layers.

Each chunk can carry:

- `source_id`
- `chunk_id`
- `section_title`
- `page_start`
- `page_end`

This makes research retrieval materially better for PDFs and long-form technical
 writing.

### 5. PDF Page Marker Contract

The PDF ingest path was upgraded to request explicit page markers in extracted
markdown using:

- `<!-- page: N -->`

That change moved page provenance from “best effort at retrieval time” to an
ingest-time extraction contract.

### 6. Corpus Evaluation

A real-document corpus eval path was added so the full cycle can be tested in a
temporary KB:

- ingest
- compile-center
- reindex
- brokered retrieval
- provenance scoring

This replaced one-off manual confidence with repeatable validation logic.

### 7. Obsidian Projection

An Obsidian-facing projection layer was added as a generated view, not as the
canonical storage layer.

That means:

- markdown source of truth stays in `second-brain`
- Obsidian is used as a projection/review surface
- the visible graph can stay centered on papers/projects/experiments/syntheses

### 8. Local MLX Runtime

Heavy LLM paths are now local-MLX-first on Apple Silicon.

This includes:

- extractor
- reconciler
- gardener model defaults
- host backend MLX chat support
- host eval judge support

This work also required upgrading the MLX runtime range to:

- `mlx-lm>=0.31,<0.32`

Older MLX versions on this machine could not load Gemma 4 or Qwen3.5 models.

## Current Local Model Stack

The current local-first model stack is:

- small extraction: `mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit`
- larger extraction: `mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit`
- deeper reconcile/gardener: `mlx/NexVeridian/gemma-4-26B-A4b-it-4bit`
- alternate local model: `mlx/mlx-community/Qwen3.5-9B-OptiQ-4bit`

Important practical note:

- text-safe Gemma 4 MLX repos worked
- some earlier Gemma 4 MLX repos did not
- the runtime also needed output sanitization because local Gemma/Qwen models
  may emit thought-channel markup rather than plain final text

The MLX clients now strip those thought-channel blocks before returning text to
the backend or component logic.

## Validation Completed

### Real Paper / Book Validation

The component was exercised on real academic documents, not just synthetic unit
fixtures.

Validated examples included:

- arXiv `2511.12640`
- Susan Athey / Stefan Wager causal inference book PDF

Those runs verified:

- PDF ingest succeeds
- page markers are preserved
- chunk manifests are created
- center paper docs compile
- brokered retrieval returns chunk-backed evidence
- page provenance is available when extraction preserved boundaries

### Local Model Validation

The following local models were downloaded and loaded successfully on this
machine:

- Gemma 4 E2B
- Gemma 4 E4B
- Gemma 4 26B A4B
- Qwen3.5 9B

Smoke generation succeeded for all of them, and the host backend `MLXClient`
was also exercised directly against the downloaded local stack.

## Host Integration Delivered

The host `claude-code-agent` backend now relies on this component through a
clearer contract.

Delivered host-side behavior includes:

- `mlx/...` model ids routed through a host MLX client
- `/api/models` exposing recommended MLX local models
- eval judge running locally through MLX instead of depending on Ollama
- backend search/prompt injection using the same brokered knowledge path
- backend knowledge mutations triggering center compile plus reindex

## Key Design Decisions That Stuck

These decisions were tested enough that they should now be treated as stable
direction, not temporary experiments:

- markdown remains canonical
- databases remain derived
- center memory stays bounded
- side memory can be large
- retrieval must return provenance, not only snippets
- Obsidian is a projection layer, not the database
- local MLX is the preferred Apple Silicon path for heavy component work

## Remaining Open Work

Important work still remains:

- deeper experiment-memory and literature-memory unification
- more retrieval evaluation coverage across a broader paper corpus
- more refined 26B prompt shaping and output control
- continued gardener/digest hardening against long-running autonomous use
- eventual cleanup of remaining Ollama-specific references that are still kept
  only for backward compatibility

## Operator Note

If you need to rehydrate the local MLX model set from the host backend, the
main preload helper lives in:

- `backend/scripts/preload_mlx_models.py`

That helper is host-side, but it is the current operational entry point for
warming the local model stack used by this component.
