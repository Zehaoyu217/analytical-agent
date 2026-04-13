from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import pandas as pd

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.skills.base import SkillError
from app.skills.data_profiler.pkg.html_report import render_html_report
from app.skills.data_profiler.pkg.report import ProfileReport
from app.skills.data_profiler.pkg.risks import Risk
from app.skills.data_profiler.pkg.sections import (
    dates,
    distributions,
    duplicates,
    keys,
    missingness,
    outliers,
    relationships,
    schema,
)

_ERRORS = {
    "EMPTY_DATAFRAME": {
        "message": "data_profiler called on empty DataFrame '{name}'.",
        "guidance": "Load data before profiling; empty DFs cannot be validated.",
        "recovery": "Inspect the source query and retry.",
    }
}


def _build_summary(name: str, n_rows: int, n_cols: int, risks: list[Risk]) -> str:
    blockers = [r for r in risks if r.severity == "BLOCKER"]
    highs = [r for r in risks if r.severity == "HIGH"]
    parts = [f"{name}: {n_rows} rows × {n_cols} cols"]
    if blockers:
        parts.append(
            f"{len(blockers)} BLOCKER(s): "
            + "; ".join(f"{r.kind} on {'/'.join(r.columns)}" for r in blockers)
        )
    if highs:
        parts.append(f"{len(highs)} HIGH")
    other = [r for r in risks if r.severity not in ("BLOCKER", "HIGH")]
    if other:
        parts.append(f"{len(other)} MEDIUM/LOW")
    return "; ".join(parts)


def profile(
    df: pd.DataFrame,
    name: str,
    key_candidates: list[str] | None = None,
    store: ArtifactStore | None = None,
    session_id: str = "default",
) -> ProfileReport:
    if df.empty:
        raise SkillError("EMPTY_DATAFRAME", {"name": name}, _ERRORS)

    section_results: dict[str, dict[str, Any]] = {
        "schema": schema.run(df),
        "missingness": missingness.run(df),
        "duplicates": duplicates.run(df, key_candidates=key_candidates),
        "distributions": distributions.run(df),
        "dates": dates.run(df),
        "outliers": outliers.run(df),
        "keys": keys.run(df, key_candidates=key_candidates),
        "relationships": relationships.run(df),
    }

    risks: list[Risk] = []
    for s in section_results.values():
        risks.extend(s.get("risks", []))
    risks.sort(key=lambda r: r.sort_key())

    n_rows = int(len(df))
    n_cols = int(len(df.columns))
    summary = _build_summary(name, n_rows, n_cols, risks)

    artifact_id = None
    report_artifact_id = None
    if store is not None:
        json_payload = {
            "name": name,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "summary": summary,
            "risks": [asdict(r) for r in risks],
            "sections": {
                k: {sk: sv for sk, sv in v.items() if sk != "risks"}
                for k, v in section_results.items()
            },
        }
        a_json = store.add_artifact(
            session_id,
            Artifact(
                type="profile",
                title=f"{name} profile",
                content=json.dumps(json_payload, default=str, indent=2),
                format="profile-json",
                profile_summary=summary,
            ),
        )
        artifact_id = a_json.id

        html = render_html_report(
            name=name,
            n_rows=n_rows,
            n_cols=n_cols,
            summary=summary,
            risks=risks,
            sections=section_results,
            df=df,
        )
        a_html = store.add_artifact(
            session_id,
            Artifact(
                type="profile",
                title=f"{name} profile — report",
                content=html,
                format="profile-html",
                profile_summary=summary,
            ),
        )
        report_artifact_id = a_html.id

    return ProfileReport(
        name=name,
        n_rows=n_rows,
        n_cols=n_cols,
        summary=summary,
        risks=risks,
        sections={
            k: {sk: sv for sk, sv in v.items() if sk != "risks"}
            for k, v in section_results.items()
        },
        artifact_id=artifact_id,
        report_artifact_id=report_artifact_id,
    )
