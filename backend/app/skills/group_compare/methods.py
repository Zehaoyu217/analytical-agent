from __future__ import annotations

from app.skills.group_compare.assumptions import AssumptionReport

VALID = frozenset({
    "auto", "student", "welch", "mann_whitney",
    "anova", "kruskal", "paired_t", "wilcoxon",
})


def pick_method(report: AssumptionReport, paired: bool, requested: str) -> str:
    if requested not in VALID:
        raise ValueError(f"unknown method: {requested}")
    if requested != "auto":
        return requested
    if paired:
        if report.k != 2:
            raise ValueError("paired design requires k=2 groups")
        return "paired_t" if report.all_normal else "wilcoxon"
    if report.k == 2:
        if not report.all_normal:
            return "mann_whitney"
        return "student" if report.homoscedastic else "welch"
    if report.k > 2:
        return "anova" if (report.all_normal and report.homoscedastic) else "kruskal"
    raise ValueError(f"unsupported k={report.k}")
