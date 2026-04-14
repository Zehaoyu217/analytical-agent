from __future__ import annotations

from collections.abc import Iterable

from app.harness.guardrails.types import GuardrailFinding, GuardrailOutcome


def apply_tier(tier: str, findings: Iterable[GuardrailFinding]) -> GuardrailOutcome:
    findings = list(findings)
    if tier == "observatory":
        return GuardrailOutcome.OBSERVE
    if not findings:
        return GuardrailOutcome.PASS
    any_fail = any(f.severity.blocks_strict() for f in findings)
    if tier == "advisory":
        return GuardrailOutcome.WARN if findings else GuardrailOutcome.PASS
    # strict
    return GuardrailOutcome.BLOCK if any_fail else GuardrailOutcome.WARN
