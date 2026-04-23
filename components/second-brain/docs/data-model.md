# Data Model

## Principle

Markdown is canonical. Databases are derived.

## Current Canonical Objects

### Sources

Stored under `sources/<slug>/`.

Important files:

- `_source.md`
- `raw/*`

### Claims

Stored under `claims/`.

Important files:

- `claims/*.md`
- `claims/resolutions/*.md`

### Habits

Stored at `.sb/habits.yaml`.

Controls:

- retrieval
- injection
- extraction density
- maintenance and digest behavior
- gardener behavior

## Derived Stores

- `graph.duckdb` for graph reasoning
- `kb.sqlite` for FTS retrieval
- `vectors.sqlite` for hybrid retrieval
- `analytics.duckdb` for maintenance and stats

## ID Rule

Frontmatter `id` should be treated as authoritative.

Filenames are useful transport and organization details, not the primary identity contract.

## Future Direction

This component is being evolved toward additional canonical objects:

- project briefs
- paper cards
- experiment cards
- synthesis notes

Those additions should preserve the same rule:

- canonical markdown first
- derived stores second
