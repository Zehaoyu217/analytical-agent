# Multicollinearity

**Slug:** `multicollinearity`
**One-liner:** Highly correlated predictors inflate standard errors and swap coefficient signs.

## What it is

When two or more predictors in a regression move together, the model cannot separate their contributions. Coefficient estimates become unstable: large standard errors, signs that flip on small data perturbations, low individual significance despite a high overall R². The joint prediction is still valid; attribution is not.

## How to detect it

- **VIF > 5** on any predictor is a yellow flag; **VIF > 10** is red.
- `data_profiler` flags `collinear_pair` for |r| > 0.9 between numeric columns.
- Coefficient signs flipping when a correlated column is added or removed.

## Mitigation

- Drop one of the colinear pair, prefer the one with stronger domain justification.
- Combine into a composite (sum, mean, PCA first component) if conceptually justified.
- Use regularized regression (ridge) for prediction; don't interpret coefficients under ridge.
- For interpretation: report the *joint* effect and skip per-variable attribution.

## See also

- `confounding`
