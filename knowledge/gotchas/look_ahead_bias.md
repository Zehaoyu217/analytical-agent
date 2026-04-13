# Look-Ahead Bias

**Slug:** `look_ahead_bias`
**One-liner:** Using information not available at the time of the event (train leakage, future joins).

## What it is

At decision time t, only information available at or before t could have been used. A feature or label that leaks post-t information into the model or analysis produces unrealistically good backtest results. Every deployment of the "brilliant" model then disappoints, because production doesn't get to see the future.

Common sources: joining on a dimension table that was updated after t, using revised macroeconomic series (revisions happen months later), labeling a churner using a horizon that extends past t.

## How to detect it

- For each feature, ask: "at time t, who knew this and when did they know it?"
- `stat_validate` looks for `as_of_column` alignment: if a model claim is made and the training frame has rows where `feature_timestamp > as_of`, WARN.
- Point-in-time join correctness: the right-hand frame must be queried with `version_ts <= as_of`.
- Gigantic out-of-sample R² with a model that uses noisy features is a smoke alarm.

## Mitigation

- Store all slowly-changing dimensions as bitemporal (valid_from / valid_to + system_ts).
- Build features with `as_of` joins; refuse to join on plain equality when `as_of` is defined.
- For backtests, replay data in the order it arrived, including revision lag.

## See also

- `multiple_comparisons`
- `immortal_time_bias`
