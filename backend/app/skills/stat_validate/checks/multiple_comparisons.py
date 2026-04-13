from __future__ import annotations

from app.skills.stat_validate.verdict import Violation

TEST_TOOLS = {
    "group_compare.compare",
    "correlation.correlate",
    "stat_validate.validate",  # self excluded below
}
P_THRESHOLD = 0.05
MAX_UNCORRECTED = 5


def check_multiple_comparisons(turn_trace: list[dict]) -> Violation | None:
    tests = [
        evt for evt in turn_trace
        if evt.get("tool") in {"group_compare.compare", "correlation.correlate"}
        and isinstance(evt.get("p_value"), (int, float))
        and float(evt["p_value"]) < P_THRESHOLD
    ]
    corrected = [evt for evt in tests if evt.get("correction")]
    uncorrected = len(tests) - len(corrected)
    if uncorrected > MAX_UNCORRECTED:
        return Violation(
            code="multiple_comparisons",
            severity="WARN",
            message=f"{uncorrected} tests at p<{P_THRESHOLD} without correction",
            gotcha_refs=("multiple_comparisons",),
        )
    return None
