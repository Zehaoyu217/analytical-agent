---
name: dashboard_builder
description: Composes KPI cards + chart artifacts into bento / grid / single_column dashboards. Exports standalone_html or a2ui. Max 12 sections, one theme per dashboard.
level: 3
version: 0.1.0
---

# dashboard_builder

Turn promoted findings + KPI cards into a dashboard artifact.

## Layouts

| Layout | Shape |
|---|---|
| `bento` (default) | Staggered 12-col grid with spanning tiles |
| `grid` | Uniform 3-col grid |
| `single_column` | Stacked, mobile-optimal |

Responsive breakpoints: 320 / 768 / 1024 / 1440.

## KPI cards

Each card: `label`, `value`, `delta`, `comparison_period`, `direction` (`"up_is_good"` or `"down_is_good"`), optional `sparkline_artifact_id`.

Delta is shown or the card shows nothing — never a placeholder. `direction` flips semantic color so churn up ≠ revenue up both get green.

## Embed modes

- `standalone_html` — self-contained HTML with inlined CSS and linked chart SVGs.
- `a2ui` — a JSON block our chat UI renders as a first-class artifact.

## Rules (enforced)

- Max 12 sections.
- No empty / placeholder cards.
- Single theme per dashboard (charts re-rendered if their theme differs).
- KPIs show delta or nothing.
