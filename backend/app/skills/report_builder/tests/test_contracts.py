# backend/app/skills/report_builder/tests/test_contracts.py
from __future__ import annotations

import pytest


def _minimal_spec_with_kp_count(n: int):
    from app.skills.report_builder.pkg.build import (
        Finding,
        FindingSection,
        Methodology,
        ReportSpec,
    )

    finding = Finding(
        id="F-20260412-001",
        title="Revenue grew 12% YoY",
        claim="Revenue up 12% vs prior year.",
        evidence_ids=("chart-ab12cd34",),
        validated_by="val-ee12ff34",
        verdict="PASS",
    )
    return ReportSpec(
        title="Q1 Report",
        author="Analytics",
        summary="One-line.",
        key_points=tuple(f"KP{i}" for i in range(n)),
        findings=(FindingSection(finding=finding, body="..."),),
        methodology=Methodology(method="t-test", data_sources=("events_v1",), caveats=("Small n",)),
        caveats=("Nothing else",),
        appendix=(),
    )


def test_research_memo_requires_three_key_points() -> None:
    from app.skills.report_builder.pkg.build import validate_spec

    with pytest.raises(ValueError, match="WRONG_KEY_POINT_COUNT"):
        validate_spec(_minimal_spec_with_kp_count(2), template="research_memo")
    with pytest.raises(ValueError, match="WRONG_KEY_POINT_COUNT"):
        validate_spec(_minimal_spec_with_kp_count(5), template="research_memo")
    # exactly 3 — OK
    validate_spec(_minimal_spec_with_kp_count(3), template="research_memo")


def test_failed_finding_blocks_build() -> None:
    from app.skills.report_builder.pkg.build import (
        Finding,
        FindingSection,
        Methodology,
        ReportSpec,
        validate_spec,
    )

    bad = Finding(
        id="F-20260412-002",
        title="Bad",
        claim="X causes Y",
        evidence_ids=("c-1",),
        validated_by="val-1",
        verdict="FAIL",
    )
    spec = ReportSpec(
        title="t",
        author="a",
        summary="s",
        key_points=("a", "b", "c"),
        findings=(FindingSection(finding=bad, body="."),),
        methodology=Methodology(method="m", data_sources=("x",), caveats=("c",)),
        caveats=("x",),
        appendix=(),
    )
    with pytest.raises(ValueError, match="FAILED_FINDING"):
        validate_spec(spec, template="research_memo")


def test_missing_methodology_fails() -> None:
    from app.skills.report_builder.pkg.build import (
        Finding,
        FindingSection,
        Methodology,
        ReportSpec,
        validate_spec,
    )

    f = Finding(
        id="F-20260412-003",
        title="t",
        claim="c",
        evidence_ids=("e-1",),
        validated_by="v-1",
        verdict="PASS",
    )
    empty_method = Methodology(method="", data_sources=(), caveats=())
    spec = ReportSpec(
        title="t",
        author="a",
        summary="s",
        key_points=("a", "b", "c"),
        findings=(FindingSection(finding=f, body="."),),
        methodology=empty_method,
        caveats=("x",),
        appendix=(),
    )
    with pytest.raises(ValueError, match="MISSING_METHODOLOGY"):
        validate_spec(spec, template="research_memo")
