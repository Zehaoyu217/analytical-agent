from __future__ import annotations

from app.harness.clients.base import ToolCall
from app.harness.guardrails.types import GuardrailFinding, Severity


def _mentions_df(code: str) -> bool:
    import re
    # word-boundary match for `df` identifier
    return bool(re.search(r"(?<![A-Za-z_.])df(?![A-Za-z0-9_])", code))


def _validate_passed_in_trace(turn_trace: list[dict]) -> bool:
    for evt in turn_trace:
        if evt.get("tool") == "stat_validate.validate":
            result = evt.get("result") or {}
            if str(result.get("status", "")).upper() == "PASS":
                return True
    return False


def _characterized_non_stationary(turn_trace: list[dict]) -> bool:
    for evt in turn_trace:
        if evt.get("tool") == "time_series.characterize":
            result = evt.get("result") or {}
            if result.get("stationary") is False:
                return True
    return False


def pre_tool_gate(
    call: ToolCall,
    turn_trace: list[dict],
    dataset_loaded: bool,
) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []

    if call.name == "sandbox.run":
        code = str(call.arguments.get("code", ""))
        if _mentions_df(code) and not dataset_loaded:
            findings.append(GuardrailFinding(
                code="df_without_dataset",
                severity=Severity.FAIL,
                message="code references `df` but no dataset is loaded in the session",
            ))

    if call.name == "promote_finding" and not _validate_passed_in_trace(turn_trace):
        findings.append(GuardrailFinding(
            code="promote_without_validate",
            severity=Severity.FAIL,
            message="promote_finding requires a prior stat_validate PASS in the turn",
        ))

    if call.name == "time_series.lag_correlate":
        accept = bool(call.arguments.get("accept_non_stationary", False))
        if not accept and _characterized_non_stationary(turn_trace):
            findings.append(GuardrailFinding(
                code="lag_corr_non_stationary",
                severity=Severity.FAIL,
                message="lag_correlate on non-stationary input requires accept_non_stationary=True",
            ))

    return findings
