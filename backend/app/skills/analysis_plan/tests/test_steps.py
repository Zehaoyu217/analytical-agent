# backend/app/skills/analysis_plan/tests/test_steps.py
from __future__ import annotations


def test_step_catalog_has_profile_and_validate() -> None:
    from app.skills.analysis_plan.pkg.steps import STEP_CATALOG

    slugs = {s.slug for s in STEP_CATALOG}
    assert "profile" in slugs
    assert "validate" in slugs


def test_quick_depth_skips_deepen() -> None:
    from app.skills.analysis_plan.pkg.steps import pick_steps

    quick = [s.slug for s in pick_steps("quick")]
    assert "deepen" not in quick
    assert "profile" in quick
    assert "report" in quick


def test_standard_depth_orders_validate_before_report() -> None:
    from app.skills.analysis_plan.pkg.steps import pick_steps

    order = [s.slug for s in pick_steps("standard")]
    assert order.index("validate") < order.index("report")
