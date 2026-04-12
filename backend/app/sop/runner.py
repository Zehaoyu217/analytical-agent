"""SOP orchestrator: pre-flight -> main triage -> propose ladder rung."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.sop.ladder_loader import load_ladder
from app.sop.preflight import run_preflight
from app.sop.triage import triage
from app.sop.types import (
    FailureReport,
    LadderRung,
    PreflightResult,
    TriageDecision,
)


class SOPResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preflight: PreflightResult
    triage: TriageDecision | None
    proposal: LadderRung | None
    advisory: str


def _advisory_for_preflight(pf: PreflightResult) -> str:
    failed = [
        name for name, v in (
            ("evaluation_bias", pf.evaluation_bias),
            ("data_quality", pf.data_quality),
            ("determinism", pf.determinism),
        ) if v == "fail"
    ]
    if failed:
        return f"Pre-flight failed: {', '.join(failed)}. Fix the eval apparatus before the agent."
    return "Pre-flight passed."


def run_sop(
    *,
    report: FailureReport,
    judge_variance: dict[str, float],
    seed_fingerprint_matches: bool,
    rerun_grades: list[str],
) -> SOPResult:
    pf = run_preflight(
        report=report,
        judge_variance=judge_variance,
        seed_fingerprint_matches=seed_fingerprint_matches,
        rerun_grades=rerun_grades,
    )
    if pf.any_failed():
        return SOPResult(
            preflight=pf, triage=None, proposal=None,
            advisory=_advisory_for_preflight(pf),
        )

    decision = triage(report)
    if decision is None:
        return SOPResult(
            preflight=pf, triage=None, proposal=None,
            advisory="No triage signal fired. Inspect trace manually.",
        )

    try:
        ladder = load_ladder(decision.bucket)
    except FileNotFoundError:
        return SOPResult(
            preflight=pf,
            triage=decision,
            proposal=None,
            advisory=f"No ladder file found for bucket '{decision.bucket}'.",
        )

    if not ladder.ladder:
        return SOPResult(
            preflight=pf,
            triage=decision,
            proposal=None,
            advisory=f"Ladder '{decision.bucket}' is empty — check YAML.",
        )

    top_rung = ladder.ladder[0]
    return SOPResult(
        preflight=pf,
        triage=decision,
        proposal=top_rung,
        advisory=f"Proposed: {top_rung.name} (cost={top_rung.cost}).",
    )
