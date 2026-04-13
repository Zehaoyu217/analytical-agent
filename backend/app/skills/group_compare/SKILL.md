---
name: group_compare
description: Compares two or more groups on a numeric variable. Auto-selects t/Welch/Mann-Whitney/ANOVA/Kruskal by assumptions. Reports effect size first, p-value second, with bootstrap CI.
level: 2
---

# Group Compare Skill

## When to use

You need to answer "is group A different from group B on metric M?" — or its k-group generalization. Always call this skill rather than running `scipy.stats.ttest_ind` directly; it picks the right test by checking assumptions, and it leads with effect size.

## Entry point

```python
from app.skills.group_compare import compare

result = compare(
    df,
    value="revenue",
    group="segment",
    paired=False,              # True for paired (same unit twice)
    paired_id=None,            # required if paired=True
    method="auto",              # or explicit: "welch"|"student"|"mann_whitney"|"anova"|"kruskal"
    bootstrap_n=1000,
)
# result.effect_size, result.effect_ci, result.effect_name    ("cohens_d" | "cliffs_delta" | "eta_sq")
# result.p_value, result.method_used, result.n_per_group, result.assumption_report
# result.artifact_id  (analysis artifact — boxplot chart + JSON)
```

## Rules

- **Effect size leads** the result and is what drives the Finding.
- Assumptions are actually tested, not assumed:
  - Normality via Shapiro-Wilk on each group (n ≤ 5000) or Anderson-Darling (n > 5000).
  - Variance equality via Levene.
- Two groups: Welch if variance-unequal, Student if variance-equal normal, Mann-Whitney if non-normal.
- k>2 groups: ANOVA if normal + homoscedastic, Kruskal-Wallis otherwise.
- Paired designs: paired t or Wilcoxon signed-rank.
- Bootstraps a 95% CI for the effect size.
- n < 10 per group → FAIL (raises).

## Outputs

`CompareResult` dataclass + `analysis` artifact with boxplot + assumption report.
