from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from app.skills.stat_validate.checks.confounder import check_confounder_risk
from app.skills.stat_validate.checks.effect_size import check_effect_size
from app.skills.stat_validate.checks.leakage import check_leakage
from app.skills.stat_validate.checks.multiple_comparisons import check_multiple_comparisons
from app.skills.stat_validate.checks.sample_size import check_sample_size
from app.skills.stat_validate.checks.simpsons import check_simpsons_paradox
from app.skills.stat_validate.checks.stationarity import check_stationarity_for_spurious
from app.skills.stat_validate.verdict import Check, Validation, Violation

VALID_KINDS = frozenset({"correlation", "group_diff", "regression", "classifier", "forecast"})


def _series_for_stationarity(
    frame: pd.DataFrame | None, payload: dict
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if frame is None:
        return None, None
    x = payload.get("x")
    y = payload.get("y")
    if x in frame.columns and y in frame.columns:
        return frame[x].dropna().to_numpy(), frame[y].dropna().to_numpy()
    return None, None


def validate(
    claim_kind: str,
    payload: dict,
    turn_trace: list[dict] | None = None,
    frame: pd.DataFrame | None = None,
    stratify_candidates: Sequence[str] = (),
    claim_text: str = "",
) -> Validation:
    if claim_kind not in VALID_KINDS:
        raise ValueError(f"stat_validate: claim_kind '{claim_kind}' unknown")

    turn_trace = turn_trace or []
    failures: list[Violation] = []
    warnings: list[Violation] = []
    passes: list[Check] = []

    def _accept(v: Violation | None, ok_msg: str, ok_code: str) -> None:
        if v is None:
            passes.append(Check(code=ok_code, message=ok_msg))
            return
        (failures if v.severity == "FAIL" else warnings).append(v)

    _accept(check_effect_size(payload), "effect size outside negligible band", "effect_size")
    _accept(check_sample_size(payload), "sample size adequate", "sample_size")
    _accept(check_multiple_comparisons(turn_trace), "no multiple-comparisons concern", "multiple_comparisons")

    if claim_kind == "correlation" and frame is not None:
        simpsons = check_simpsons_paradox(payload, frame=frame,
                                          stratify_candidates=stratify_candidates)
        _accept(simpsons, "no Simpson's reversal found", "simpsons_paradox")

    if claim_kind in {"correlation", "regression", "classifier"}:
        _accept(
            check_confounder_risk(payload, claim_text=claim_text),
            "no causal language or controls present",
            "confounder_risk",
        )

    if claim_kind == "correlation":
        x_arr, y_arr = _series_for_stationarity(frame, payload)
        _accept(
            check_stationarity_for_spurious(payload, x_arr, y_arr),
            "stationarity / detrending OK for correlation",
            "stationarity",
        )

    _accept(check_leakage(payload), "no leakage detected", "leakage")

    return Validation(
        status="PASS",  # overwritten by rollup_status() consumers
        failures=tuple(failures),
        warnings=tuple(warnings),
        passes=tuple(passes),
    )
