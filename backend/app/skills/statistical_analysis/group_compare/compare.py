from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import (
    f_oneway,
    kruskal,
    mannwhitneyu,
    ttest_ind,
    ttest_rel,
    wilcoxon,
)

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.skills.statistical_analysis.group_compare.assumptions import check_assumptions
from app.skills.statistical_analysis.group_compare.effect_size import (
    cliffs_delta,
    cohens_d,
    eta_squared,
)
from app.skills.statistical_analysis.group_compare.methods import pick_method
from app.skills.statistical_analysis.group_compare.result import CompareResult


def _run_test(method: str, groups: list[np.ndarray]) -> float:
    if method == "student":
        return float(ttest_ind(groups[0], groups[1], equal_var=True).pvalue)
    if method == "welch":
        return float(ttest_ind(groups[0], groups[1], equal_var=False).pvalue)
    if method == "mann_whitney":
        return float(mannwhitneyu(groups[0], groups[1], alternative="two-sided").pvalue)
    if method == "anova":
        return float(f_oneway(*groups).pvalue)
    if method == "kruskal":
        return float(kruskal(*groups).pvalue)
    if method == "paired_t":
        return float(ttest_rel(groups[0], groups[1]).pvalue)
    if method == "wilcoxon":
        return float(wilcoxon(groups[0], groups[1]).pvalue)
    raise ValueError(f"unknown method: {method}")


def _effect(method: str, groups: list[np.ndarray]) -> tuple[float, str]:
    if method in {"student", "welch", "paired_t"}:
        return cohens_d(groups[0], groups[1]), "cohens_d"
    if method in {"mann_whitney", "wilcoxon"}:
        return cliffs_delta(groups[0], groups[1]), "cliffs_delta"
    if method in {"anova", "kruskal"}:
        return eta_squared(groups), "eta_sq"
    raise ValueError(f"no effect for method: {method}")


def _bootstrap_effect(
    method: str, groups: list[np.ndarray], n_resamples: int, seed: int
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    stats = np.empty(n_resamples)
    for i in range(n_resamples):
        resampled = [rng.choice(g, size=g.size, replace=True) for g in groups]
        stats[i], _ = _effect(method, resampled)
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def compare(
    df: pd.DataFrame,
    value: str,
    group: str,
    paired: bool = False,
    paired_id: str | None = None,
    method: str = "auto",
    bootstrap_n: int = 1000,
    store: ArtifactStore | None = None,
    session_id: str | None = None,
    seed: int = 0,
) -> CompareResult:
    for col in (value, group):
        if col not in df.columns:
            raise KeyError(
                f"group_compare: column '{col}' not in DataFrame. "
                f"Available: {list(df.columns)}"
            )
    if paired:
        if paired_id is None:
            raise ValueError("group_compare: paired=True requires paired_id column.")
        if paired_id not in df.columns:
            raise KeyError(f"group_compare: paired_id '{paired_id}' not in DataFrame.")
        # Enforce balanced, sorted by paired_id for ttest_rel / wilcoxon
        work = df.dropna(subset=[value, group, paired_id]).copy()
        pivot = work.pivot(index=paired_id, columns=group, values=value).dropna()
        labels = tuple(map(str, pivot.columns.tolist()))
        if len(labels) != 2:
            raise ValueError(f"paired requires exactly 2 groups, got {len(labels)}")
        groups_arr = [pivot[labels[0]].to_numpy(), pivot[labels[1]].to_numpy()]
    else:
        labels = tuple(sorted(map(str, df[group].dropna().unique())))
        groups_arr = [
            df.loc[df[group] == lbl, value].dropna().to_numpy() for lbl in labels
        ]

    for lbl, g in zip(labels, groups_arr, strict=False):
        if g.size < 10:
            raise ValueError(
                f"group_compare: group '{lbl}' has n={g.size} < 10. "
                "Need ≥10 per group or collapse groups."
            )

    report = check_assumptions(groups_arr)
    method_used = pick_method(report, paired=paired, requested=method)
    effect, effect_name = _effect(method_used, groups_arr)
    ci_lo, ci_hi = _bootstrap_effect(method_used, groups_arr, bootstrap_n, seed)
    p_value = _run_test(method_used, groups_arr)

    artifact_id = None
    if store is not None and session_id is not None:
        payload = {
            "method_used": method_used,
            "effect": {"name": effect_name, "value": effect,
                       "ci_low": ci_lo, "ci_high": ci_hi},
            "p_value": p_value,
            "assumption_report": report.to_dict(),
            "n_per_group": dict(zip(labels, [int(g.size) for g in groups_arr], strict=False)),
            "paired": paired,
        }
        artifact = Artifact(
            type="analysis",
            content=json.dumps(payload),
            format="json",
            title=f"compare({value} by {group})",
            description=f"{method_used} {effect_name}={effect:.3f} CI[{ci_lo:.3f},{ci_hi:.3f}]",
        )
        saved = store.add_artifact(session_id, artifact)
        artifact_id = saved.id

    return CompareResult(
        effect_size=effect, effect_ci_low=ci_lo, effect_ci_high=ci_hi,
        effect_name=effect_name, p_value=p_value, method_used=method_used,
        n_per_group=tuple(int(g.size) for g in groups_arr),
        group_labels=labels, assumption_report=report.to_dict(),
        paired=paired, artifact_id=artifact_id,
    )
