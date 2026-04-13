# Survivorship Bias

**Slug:** `survivorship_bias`
**One-liner:** Analyzing only survivors (funds, firms, patients) biases results toward positive outcomes.

## What it is

The special case of selection bias where the filter is "still exists at time of analysis". Mutual fund databases that delete dead funds show the surviving funds' returns — a strictly positive bias. Same pattern: WWII bombers (Wald), successful startup patterns, "10 habits of effective people".

## How to detect it

- Does the dataset describe a process with exits (death, delisting, churn, failure)?
- Are exited units present, or have they been removed/backfilled?
- Baseline: compare summary stats to a source that includes exits (CRSP deletion files, SSA mortality tables, etc.).

## Mitigation

- Obtain the deletions/exits and merge them in with outcome="dead".
- If you can't, compute the effect on a cohort defined at a past date (cohort starting 2015-01-01, followed forward), not a snapshot of survivors today.
- Caveat the Finding: "Results reflect surviving <units> as of <date>; dead <units> not observed."

## See also

- `selection_bias`
- `immortal_time_bias`
- Reference: Wald (1943), the classic bombers-returning-from-missions analysis.
