---
name: statistical_analysis
description: "Statistical tests and analysis: correlation, distribution fitting, group comparison, assumption validation, and time-series. Load sub-skills to proceed."
version: "0.1"
---

# Statistical Analysis

Hub for statistical analysis capabilities. Load the appropriate sub-skill for your task.

## Choosing a sub-skill

| Task | Sub-skill |
|------|-----------|
| Measure relationship between two variables | `correlation` |
| Fit a parametric distribution to a variable | `distribution_fit` |
| Compare means/medians across groups | `group_compare` |
| Validate statistical assumptions before analysis | `stat_validate` |
| Decompose, forecast, or detect anomalies in time-series | `time_series` |

## Workflow

Always validate assumptions (`stat_validate`) before drawing conclusions.
`stat_validate` should run after `correlation`, `group_compare`, or `distribution_fit`
to confirm the test's preconditions were met.
