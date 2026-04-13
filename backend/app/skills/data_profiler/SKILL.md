---
name: data_profiler
description: Full-dataset profile. Runs before analysis; surfaces structured risks (missing, dupes, keys, outliers, dates, skew) with BLOCKER/HIGH/MEDIUM/LOW severity. Emits a machine-readable JSON artifact and a human-readable HTML report.
level: 1
version: '0.1'
---
# data_profiler

One call, eight sections, structured risks. Agents should call this on any unfamiliar dataset before analyzing. If a BLOCKER is raised, resolve it first.

## When to use

First turn on a new dataset. Optionally again after a transformation that changed the shape (merges, joins, filters).

## Contract

```python
report = profile(df, name="customers_v1", key_candidates=["customer_id"])
# report.summary             — one-paragraph, model-readable
# report.risks               — severity-sorted Risk list
# report.sections            — full section payloads
# report.artifact_id         — profile-json artifact
# report.report_artifact_id  — profile-html artifact
```

## Sections

1. `schema` — types, counts, null counts.
2. `missingness` — per-column missing %; co-occurrence between columns.
3. `duplicates` — duplicate rows; duplicate keys (if `key_candidates` given).
4. `distributions` — skew, kurtosis, near-constant detection.
5. `dates` — monotonicity, gaps, future dates, naive timezones.
6. `outliers` — IQR + p0.001/p0.999 tail.
7. `keys` — cardinality; suspected foreign keys to passed `key_candidates`.
8. `relationships` — pairwise correlations and collinear pairs (|r| > 0.95).

## Risk severities

- `BLOCKER` — analysis should stop until resolved (duplicate key, >50% missing on a required col).
- `HIGH` — must be disclosed in any Finding using the affected columns.
- `MEDIUM` — worth noting in COT.
- `LOW` — informational.

Every risk has a `mitigation` string.
