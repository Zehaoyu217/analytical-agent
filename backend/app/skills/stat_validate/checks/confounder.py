from __future__ import annotations

import re

from app.skills.stat_validate.verdict import Violation

CAUSAL_PATTERNS = (
    r"\bcauses?\b",
    r"\bdrives?\b",
    r"\bleads? to\b",
    r"\bresults? in\b",
    r"\bincreases?\b.+\bbecause\b",
    r"\bexplains?\b.+\b(rise|drop|increase|decrease)\b",
)


def _looks_causal(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(p, lowered) for p in CAUSAL_PATTERNS)


def check_confounder_risk(payload: dict, claim_text: str) -> Violation | None:
    if not _looks_causal(claim_text):
        return None
    partial_on = payload.get("partial_on") or []
    controls = payload.get("controls") or []
    if partial_on or controls:
        return None
    return Violation(
        code="confounder_risk",
        severity="WARN",
        message="causal-shaped claim without partial_on / controls",
        gotcha_refs=("confounding",),
    )
