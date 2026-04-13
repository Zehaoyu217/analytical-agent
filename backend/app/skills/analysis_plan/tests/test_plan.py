# backend/app/skills/analysis_plan/tests/test_plan.py
from __future__ import annotations

from pathlib import Path

import pytest


def test_plan_rejects_empty_question() -> None:
    from app.skills.analysis_plan.pkg.plan import plan

    with pytest.raises(ValueError, match="EMPTY_QUESTION"):
        plan("   ")


def test_plan_standard_depth_produces_named_steps() -> None:
    from app.skills.analysis_plan.pkg.plan import plan

    result = plan("Does churn correlate with weekly active minutes?", dataset="events_v1")
    slugs = [s.slug for s in result.steps]
    assert slugs[0] == "orient"
    assert "profile" in slugs
    assert slugs[-1] == "report"
    assert result.question.startswith("Does churn")
    assert result.dataset == "events_v1"


def test_plan_writes_to_working_md(tmp_path: Path, monkeypatch) -> None:
    from app.skills.analysis_plan.pkg import plan as plan_mod

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    monkeypatch.setattr(plan_mod, "WIKI_DIR", wiki)

    result = plan_mod.plan("Why did MRR drop in Q2?", depth="quick")
    working = (wiki / "working.md").read_text()
    assert "TODO" in working
    assert result.steps[0].slug in working
    assert "Why did MRR drop in Q2?" in working
