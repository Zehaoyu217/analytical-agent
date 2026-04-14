# backend/app/skills/dashboard_builder/tests/test_contracts.py
from __future__ import annotations

import pytest


def _kpi(**overrides):
    from app.skills.dashboard_builder.pkg.build import KPICard

    base = dict(
        label="MRR",
        value=1250000.0,
        delta=0.12,
        comparison_period="last quarter",
        direction="up_is_good",
        sparkline_artifact_id=None,
        unit="USD",
    )
    base.update(overrides)
    return KPICard(**base)


def _kpi_section(**kw):
    from app.skills.dashboard_builder.pkg.build import SectionSpec

    return SectionSpec(kind="kpi", span=3, payload=_kpi(**kw))


def _spec(sections):
    from app.skills.dashboard_builder.pkg.build import DashboardSpec

    return DashboardSpec(
        title="KPI Dash",
        author="a",
        layout="bento",
        sections=tuple(sections),
        theme_variant="light",
        subtitle=None,
    )


def test_too_many_sections_raises() -> None:
    from app.skills.dashboard_builder.pkg.build import validate_spec

    sections = [_kpi_section() for _ in range(13)]
    with pytest.raises(ValueError, match="TOO_MANY_SECTIONS"):
        validate_spec(_spec(sections))


def test_empty_dashboard_raises() -> None:
    from app.skills.dashboard_builder.pkg.build import validate_spec

    with pytest.raises(ValueError, match="EMPTY_DASHBOARD"):
        validate_spec(_spec([]))


def test_kpi_without_delta_raises() -> None:
    from app.skills.dashboard_builder.pkg.build import validate_spec

    with pytest.raises(ValueError, match="KPI_NO_DELTA"):
        validate_spec(_spec([_kpi_section(delta=None)]))


def test_unknown_direction_raises() -> None:
    from app.skills.dashboard_builder.pkg.build import validate_spec

    with pytest.raises(ValueError, match="UNKNOWN_DIRECTION"):
        validate_spec(
            _spec(
                [
                    _kpi_section(direction="sideways"),
                ]
            )
        )


def test_unknown_layout_raises() -> None:
    from app.skills.dashboard_builder.pkg.build import DashboardSpec, validate_spec

    spec = DashboardSpec(
        title="t",
        author="a",
        layout="pinwheel",
        sections=(_kpi_section(),),
        theme_variant="light",
        subtitle=None,
    )
    with pytest.raises(ValueError, match="UNKNOWN_LAYOUT"):
        validate_spec(spec)
