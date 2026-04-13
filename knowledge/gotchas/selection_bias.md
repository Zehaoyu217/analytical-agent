# Selection Bias

**Slug:** `selection_bias`
**One-liner:** Conditioning on the outcome or a non-random sample breaks inference about the population.

## What it is

The data available to you is a non-random slice of the population: customers who answered the survey, patients who showed up for follow-up, stocks still listed today. Whatever generated the filtering is almost always correlated with the variables you care about, so sample statistics ≠ population statistics.

## How to detect it

- Ask: what produced this dataset? Is there a way a unit could be excluded that depends on X or Y?
- Check for truncation at thresholds (e.g., no values below $1 — minimum order filter).
- Compare to a known-universal baseline (population census, exchange listing) where possible.

## Mitigation

- Restate the population: "customers who completed the survey", not "customers".
- **Heckman correction** when you can model the selection process.
- **Inverse-probability weighting** when you have a reference distribution.
- Report the selection mechanism explicitly in the Finding's caveats section.

## See also

- `survivorship_bias`
- `berksons_paradox`
- `immortal_time_bias`
