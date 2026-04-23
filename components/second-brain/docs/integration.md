# Integration

## Embedded In `claude-code-agent`

The host app integrates `second-brain` through:

- Python package import: `second_brain`
- backend tool handlers in `backend/app/tools`
- backend REST routes in `backend/app/api`
- prompt-time recall wiring in the harness
- `.claude/settings.json` shell hooks

Current integrated behavior includes:

- backend `sb_search` using the shared broker path
- backend prompt injection using the same brokered recall path
- backend ingest / claim-promotion tools auto-running center compile + reindex so new knowledge becomes searchable immediately
- backend broker responses exposing evidence provenance from chunk retrieval when available
- backend broker responses exposing top-level provenance on direct chunk hits as well as evidence-level provenance on linked center hits
- component live LLM paths now routing to local MLX models by default on Apple Silicon, rather than assuming Anthropic-only extract / reconcile clients
- backend `second-brain` extra now installs `second-brain[mlx]`, so the host environment matches the component's default local runtime

## Retrieval Payload Contract

The host should treat these search fields as part of the stable integration surface:

- `id`
- `kind`
- `title`
- `score`
- `matched_field`
- `summary`
- `section_title`
- `page_start`
- `page_end`
- `evidence[]`

Evidence rows may additionally carry:

- `source_id`
- `chunk_id`
- `source_title`

This matters because a frontend or tool wrapper that strips those fields turns high-quality academic recall back into unverifiable snippets.

## Packaging

The backend package points at the nested component through a local source dependency rather than an absolute sibling path.

This keeps the component:

- portable inside the repo
- editable in place
- testable without a separate checkout

## Expected Host Responsibilities

The host app should:

- resolve `SECOND_BRAIN_HOME`
- expose feature flags such as `SECOND_BRAIN_ENABLED`
- translate component behavior into user-facing routes and tools
- not bypass canonical component contracts
- preserve provenance fields end to end when adapting component search results
- surface chunk ids to debugging and inspection paths, because `sb load chk_*` is now a valid operator path

## Important Boundary Rule

`claude-code-agent` may wrap the component, but it should not become the only place where component behavior is understandable.

If a lifecycle or maintenance rule matters, it should be documented and testable inside this component as well.

## Current Reliability Boundary

The host should not promise exact PDF page citation quality unless the ingest stack preserved page markers in `_source.md`.

Current guarantee:

- chunk retrieval works
- section provenance often works when headings survive extraction
- page provenance works when page boundaries survive extraction; for PDFs the component now explicitly requests markdown page separators from the converter to improve that path
