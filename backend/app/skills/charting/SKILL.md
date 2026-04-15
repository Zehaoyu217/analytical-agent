---
name: charting
description: "Visualization capabilities using Altair: bar, line, scatter, histogram, heatmap, and more. Load sub-skills for chart-specific guidance."
version: "0.1"
---

# Charting

Hub for all chart types. The `altair_charts` sub-skill provides the chart generation
functions available in the sandbox.

## When to load this hub

Load `charting` first when you need to produce any chart. Then load `altair_charts`
to see the specific chart functions, their parameters, and expected data shapes.

## Altair theme

All charts use the project theme. Call `ensure_registered()` and `use_variant("dark")`
(or `"light"`) before generating charts. This is pre-run in the sandbox bootstrap.
