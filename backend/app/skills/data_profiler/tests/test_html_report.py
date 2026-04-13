from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_html_report_uses_editorial_surface_color(small_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.html_report import render_html_report
    from app.skills.data_profiler.pkg.sections import schema

    sec = {"schema": schema.run(small_df)}
    html = render_html_report(
        name="customers_v1",
        n_rows=len(small_df),
        n_cols=len(small_df.columns),
        summary="summary",
        risks=[],
        sections=sec,
        df=small_df,
    )
    assert "<html" in html.lower()
    assert "#FBF7EE" in html  # editorial base


def test_html_report_lists_risks_sorted_with_blocker_first(
    duplicated_key_df: pd.DataFrame,
) -> None:
    from app.skills.data_profiler.pkg.html_report import render_html_report
    from app.skills.data_profiler.pkg.risks import Risk

    risks = [
        Risk(
            kind="duplicate_key",
            severity="BLOCKER",
            columns=("customer_id",),
            detail="d",
            mitigation="m",
        ),
        Risk(
            kind="duplicate_rows",
            severity="HIGH",
            columns=("a", "b"),
            detail="d",
            mitigation="m",
        ),
    ]
    html = render_html_report(
        name="x",
        n_rows=4,
        n_cols=2,
        summary="s",
        risks=risks,
        sections={},
        df=duplicated_key_df,
    )
    assert html.index("BLOCKER") < html.index("HIGH")
