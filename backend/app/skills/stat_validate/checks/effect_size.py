from __future__ import annotations

from app.skills.stat_validate.verdict import Violation

NEGLIGIBLE = 0.10


def check_effect_size(payload: dict) -> Violation | None:
    effect = payload.get("effect")
    if effect is None:
        # claim shape without effect (e.g. correlation result with coefficient/ci_low/ci_high)
        if all(k in payload for k in ("coefficient", "ci_low", "ci_high")):
            lo, hi = float(payload["ci_low"]), float(payload["ci_high"])
            name = "pearson_r"
        else:
            return None
    else:
        lo, hi = float(effect["ci_low"]), float(effect["ci_high"])
        name = str(effect.get("name", "effect"))
    if -NEGLIGIBLE < lo < NEGLIGIBLE and -NEGLIGIBLE < hi < NEGLIGIBLE:
        return Violation(
            code="effect_size_negligible",
            severity="FAIL",
            message=f"{name} CI [{lo:.3f}, {hi:.3f}] entirely within negligible band ±{NEGLIGIBLE}",
            gotcha_refs=(),
        )
    return None
