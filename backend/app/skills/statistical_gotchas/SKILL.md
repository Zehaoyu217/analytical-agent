---
name: statistical_gotchas
description: "Reference guide for 14 statistical pitfalls (Simpson's paradox, survivorship bias, look-ahead bias, etc.). Load before interpreting correlations, regressions, or pre-post comparisons."
version: "0.1"
---

# Statistical Gotchas

A reference of the 14 most common statistical pitfalls in data analysis. Check the relevant section before interpreting results or presenting findings — one missed gotcha can invalidate a conclusion.

## Gotcha Catalog

- **base_rate_neglect** — Ignoring prior probability when interpreting a test result or conditional claim.
- **berksons_paradox** — Selection into a sample creates spurious negative correlation between independent traits.
- **confounding** — A third variable drives both X and Y; the X↔Y correlation is real but causally misleading.
- **ecological_fallacy** — Inferring individual-level relationships from group-level aggregates.
- **immortal_time_bias** — Cohort definitions that guarantee survival during a look-back window inflate treatment effects.
- **look_ahead_bias** — Using information not available at the time of the event (train leakage, future joins).
- **multicollinearity** — Highly correlated predictors inflate standard errors and swap coefficient signs.
- **multiple_comparisons** — Running many tests without correction turns noise into "discoveries".
- **non_stationarity** — Mean/variance/autocorrelation drift invalidates correlations, tests, and models assuming iid data.
- **regression_to_mean** — Extreme values move toward the mean on remeasurement; pre-post designs without controls fake treatment effects.
- **selection_bias** — Conditioning on the outcome or a non-random sample breaks inference about the population.
- **simpsons_paradox** — A trend visible in subgroups reverses when aggregated (or vice versa).
- **spurious_correlation** — Two unrelated series share trend/seasonality and look correlated without a real link.
- **survivorship_bias** — Analyzing only survivors (funds, firms, patients) biases results toward positive outcomes.

## When to Apply

| Situation | Gotchas to check |
|-----------|-----------------|
| Measuring correlation between two variables | `confounding`, `spurious_correlation`, `simpsons_paradox` |
| Pre-post comparison without a control group | `regression_to_mean`, `immortal_time_bias` |
| Training or evaluating a model on historical data | `look_ahead_bias`, `selection_bias`, `survivorship_bias` |
| Running multiple significance tests | `multiple_comparisons` |
| Comparing aggregate vs. individual-level patterns | `ecological_fallacy`, `simpsons_paradox` |
| Interpreting regression coefficients | `multicollinearity`, `confounding` |
| Working with time-series data | `non_stationarity`, `spurious_correlation` |
| Interpreting a test or screening result | `base_rate_neglect`, `berksons_paradox` |

## Loading Full Gotcha Guides

Full per-gotcha guides with worked examples and remediation steps are in `knowledge/gotchas/<slug>.md`. Load a specific guide when you need the complete treatment:

```python
# Read the full Simpson's Paradox guide
read_file("knowledge/gotchas/simpsons_paradox.md")

# Read look-ahead bias guidance before building a training set
read_file("knowledge/gotchas/look_ahead_bias.md")
```
