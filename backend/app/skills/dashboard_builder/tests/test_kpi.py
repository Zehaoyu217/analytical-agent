# backend/app/skills/dashboard_builder/tests/test_kpi.py
from __future__ import annotations


def test_positive_delta_up_is_good_is_positive_class() -> None:
    from app.skills.dashboard_builder.pkg.build import KPICard
    from app.skills.dashboard_builder.pkg.kpi import render_kpi_tile

    card = KPICard(
        label="MRR",
        value=1_250_000,
        delta=0.12,
        comparison_period="last Q",
        direction="up_is_good",
        sparkline_artifact_id=None,
        unit="USD",
    )
    tile = render_kpi_tile(card)
    assert tile.delta_class == "positive"
    assert "+12" in tile.delta_str


def test_positive_delta_down_is_good_is_negative_class() -> None:
    from app.skills.dashboard_builder.pkg.build import KPICard
    from app.skills.dashboard_builder.pkg.kpi import render_kpi_tile

    card = KPICard(
        label="Churn",
        value=0.047,
        delta=0.003,
        comparison_period="last Q",
        direction="down_is_good",
        sparkline_artifact_id=None,
        unit="",
    )
    tile = render_kpi_tile(card)
    assert tile.delta_class == "negative"


def test_value_with_usd_unit_formats_with_currency() -> None:
    from app.skills.dashboard_builder.pkg.build import KPICard
    from app.skills.dashboard_builder.pkg.kpi import render_kpi_tile

    card = KPICard(
        label="MRR",
        value=1_250_000,
        delta=0.12,
        comparison_period="last Q",
        direction="up_is_good",
        sparkline_artifact_id=None,
        unit="USD",
    )
    tile = render_kpi_tile(card)
    assert "$" in tile.value or "USD" in tile.value
