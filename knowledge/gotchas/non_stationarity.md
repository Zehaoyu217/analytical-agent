# Non-Stationarity

**Slug:** `non_stationarity`
**One-liner:** Mean/variance/autocorrelation drift invalidates correlations, tests, and models assuming iid data.

## What it is

A stationary time series has a constant mean, constant variance, and autocorrelation that depends only on lag. A non-stationary one drifts: trending mean, changing variance, regime shifts. Applying Pearson correlation, t-tests, or classical regression to non-stationary series produces confident nonsense.

## How to detect it

- **ADF test** p > 0.05: cannot reject unit root → likely non-stationary.
- **KPSS test** p < 0.05: reject stationarity around a trend.
- `time_series` skill runs both (combined verdict: stationary only if ADF rejects unit root AND KPSS does not reject stationarity).
- Visual: rolling mean or rolling variance that changes over time.

## Mitigation

- **Difference** until stationary (usually first difference suffices).
- **Detrend** (subtract a linear or STL trend).
- **Log-transform** variance that grows with level.
- If using correlation on levels, explicitly name the level-correlation caveat in the Finding.

## See also

- `spurious_correlation`
- `regression_to_mean`
