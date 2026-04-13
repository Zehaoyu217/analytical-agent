from __future__ import annotations

from app.skills.stat_validate.verdict import Violation

MIN_N = 10


def check_sample_size(payload: dict) -> Violation | None:
    n_per_group = payload.get("n_per_group")
    if isinstance(n_per_group, dict):
        small = {k: v for k, v in n_per_group.items() if v < MIN_N}
        if small:
            return Violation(
                code="sample_size_small",
                severity="FAIL",
                message=f"groups below n={MIN_N}: {small}",
            )
    n = payload.get("n_effective")
    if isinstance(n, (int, float)) and n < MIN_N:
        return Violation(
            code="sample_size_small",
            severity="FAIL",
            message=f"n_effective={int(n)} < {MIN_N}",
        )
    return None
