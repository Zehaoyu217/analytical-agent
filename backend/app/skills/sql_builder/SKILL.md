---
name: sql_builder
description: DuckDB query helpers — safe field quoting, paginated SELECTs, column stats.
level: 1
version: '0.1'
---
# sql_builder

Composes DuckDB SQL safely from field lists. No string interpolation of user values — field names are quoted with `"` and any non-identifier input raises.

## When to use

When another skill needs to scan a DataFrame via DuckDB for speed (large tables, grouping, window functions).

## Contract

- `quote(ident: str) -> str`: returns `"ident"`; raises `ValueError` if the string is not a safe identifier.
- `select(table, columns, where=None, limit=None) -> str`
- `groupby_counts(table, column) -> str`
- `summary_stats(table, column) -> str` — returns a SELECT that yields `count, nulls, min, max, mean, stddev, p01, p05, p50, p95, p99` for a numeric column.

## Errors

`NOT_IDENTIFIER` — identifier contains characters outside `[A-Za-z_][A-Za-z0-9_]*`.
