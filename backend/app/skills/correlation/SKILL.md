---
name: correlation
description: Auto-selects Pearson/Spearman/Kendall/distance/partial correlation with bootstrap CI and nonlinear detection. Never silently drops NA.
level: 2
---

# Correlation Skill

## When to use

You want to quantify the strength of relationship between two numeric variables, or a target with several candidate numerics. Always call this skill rather than `numpy.corrcoef` or `pandas.corr` directly — those silently drop NaN and hide nonlinear relationships.

## Entry point

```python
from app.skills.correlation import correlate

result = correlate(
    df,
    x="price",
    y="quantity",
    method="auto",            # or "pearson"|"spearman"|"kendall"|"distance"
    partial_on=None,           # list[str] — partial correlation
    detrend=None,              # None|"difference"|"stl_residual"
    bootstrap_n=1000,
    handle_na="report",        # "report"|"drop"|"fail"
)
# result.coefficient, result.ci_low, result.ci_high, result.p_value
# result.method_used, result.nonlinear_warning, result.n_effective, result.na_dropped
# result.artifact_id (analysis artifact — includes scatter chart)
```

## Rules

- `method="auto"` picks Spearman if monotonic-nonlinear detected, else Pearson.
- Always bootstraps CI via 1000 resamples (override with `bootstrap_n`).
- Emits `nonlinear_warning=True` if |spearman − pearson| > 0.1.
- `handle_na="report"` (default) returns `n_effective` and `na_dropped` so the caller sees the loss.
- `partial_on=[z]` computes partial correlation via residuals from OLS on z.
- Refuses non-stationary inputs without `detrend=...` when inputs fail ADF.

## Outputs

`CorrelationResult` dataclass + `analysis` artifact carrying the scatter-trend chart + a JSON blob.
