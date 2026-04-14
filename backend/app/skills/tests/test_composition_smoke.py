# backend/app/skills/tests/test_composition_smoke.py
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def test_plan_chart_report_dashboard_end_to_end(tmp_path: Path, monkeypatch) -> None:
    # 1. Plan
    from app.skills.analysis_plan.pkg import plan as plan_mod

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    monkeypatch.setattr(plan_mod, "WIKI_DIR", wiki)
    plan_result = plan_mod.plan(
        "Did Q1 revenue beat forecast?",
        dataset="rev_v1",
        depth="standard",
    )
    assert "profile" in [s.slug for s in plan_result.steps]

    # 2. Charts
    from app.skills.altair_charts.pkg.actual_vs_forecast import actual_vs_forecast
    from app.skills.altair_charts.pkg.grouped_bar import grouped_bar

    ts = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6, freq="ME"),
            "actual": [100, 102, 104, 108, None, None],
            "forecast": [None, None, None, 108, 110, 112],
        }
    )
    chart_avf = actual_vs_forecast(ts, x="date", actual="actual", forecast="forecast")
    assert "layer" in chart_avf.to_dict()

    bar_df = pd.DataFrame({"region": ["N", "S"], "rev": [5.0, 9.0], "period": ["Q1", "Q1"]})
    chart_bar = grouped_bar(bar_df, x="region", y="rev", category="period")
    assert chart_bar.to_dict()["encoding"]["xOffset"]["field"] == "period"

    # 3. Report
    from app.skills.report_builder.pkg import build as report_build_mod
    from app.skills.report_builder.pkg.build import (
        Finding,
        FindingSection,
        Methodology,
        ReportSpec,
    )

    finding = Finding(
        id="F-20260412-SMOKE",
        title="Rev beat forecast by 3%",
        claim="Actual rev exceeded forecast.",
        evidence_ids=("chart-avf000001",),
        validated_by="val-abcd1234",
        verdict="PASS",
    )
    spec = ReportSpec(
        title="Smoke Report",
        author="CI",
        summary="Summary",
        key_points=("a", "b", "c"),
        findings=(FindingSection(finding=finding, body="body"),),
        methodology=Methodology(method="diff", data_sources=("rev_v1",), caveats=("m",)),
        caveats=("c",),
        appendix=(),
    )
    monkeypatch.setattr(report_build_mod, "_OUTPUT_DIR", tmp_path / "reports")
    rep = report_build_mod.build(spec, template="research_memo", formats=("md", "html"), session_id="sess")
    assert rep.paths["md"].exists()

    # 4. Dashboard
    from app.skills.dashboard_builder.pkg import build as dash_build_mod
    from app.skills.dashboard_builder.pkg.build import (
        DashboardSpec,
        KPICard,
        SectionSpec,
    )

    dspec = DashboardSpec(
        title="Smoke Dash",
        author="CI",
        layout="bento",
        sections=(
            SectionSpec(
                kind="kpi",
                span=3,
                payload=KPICard(
                    label="MRR",
                    value=1_000_000,
                    delta=0.03,
                    comparison_period="Q1 forecast",
                    direction="up_is_good",
                    sparkline_artifact_id=None,
                    unit="USD",
                ),
            ),
            SectionSpec(kind="chart", span=9, payload="chart-avf000001", title="Revenue"),
        ),
        theme_variant="light",
        subtitle=None,
    )
    a2ui = dash_build_mod.build(dspec, mode="a2ui", session_id="sess")
    assert a2ui.a2ui_payload["title"] == "Smoke Dash"
    assert len(a2ui.a2ui_payload["tiles"]) == 2
    # Serializes cleanly.
    assert json.dumps(a2ui.a2ui_payload)
