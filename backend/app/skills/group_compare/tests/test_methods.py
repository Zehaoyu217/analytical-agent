from __future__ import annotations

from app.skills.group_compare.assumptions import AssumptionReport
from app.skills.group_compare.methods import pick_method


def _report(k: int, all_normal: bool, homo: bool) -> AssumptionReport:
    return AssumptionReport(
        k=k, n_per_group=(50,) * k, all_normal=all_normal,
        normal_per_group=(all_normal,) * k,
        homoscedastic=homo, levene_p=0.5 if homo else 0.001,
    )


def test_two_group_normal_homo_picks_student() -> None:
    assert pick_method(_report(2, True, True), paired=False, requested="auto") == "student"


def test_two_group_normal_hetero_picks_welch() -> None:
    assert pick_method(_report(2, True, False), paired=False, requested="auto") == "welch"


def test_two_group_nonnormal_picks_mann_whitney() -> None:
    assert pick_method(_report(2, False, True), paired=False, requested="auto") == "mann_whitney"


def test_three_group_normal_homo_picks_anova() -> None:
    assert pick_method(_report(3, True, True), paired=False, requested="auto") == "anova"


def test_three_group_nonnormal_picks_kruskal() -> None:
    assert pick_method(_report(3, False, True), paired=False, requested="auto") == "kruskal"


def test_two_group_paired_normal_picks_paired_t() -> None:
    assert pick_method(_report(2, True, True), paired=True, requested="auto") == "paired_t"


def test_two_group_paired_nonnormal_picks_wilcoxon() -> None:
    assert pick_method(_report(2, False, True), paired=True, requested="auto") == "wilcoxon"


def test_explicit_method_wins() -> None:
    assert pick_method(_report(2, True, True), paired=False, requested="welch") == "welch"
