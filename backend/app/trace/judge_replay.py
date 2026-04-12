"""Judge variance replayer: cached path + live re-run escape hatch."""
from __future__ import annotations

from collections.abc import Callable
from statistics import pstdev

from app.trace.events import FinalOutputEvent, JudgeRun, Trace

LiveRunner = Callable[[str, int], list[JudgeRun]]


class MissingApiKeyError(RuntimeError):
    pass


def compute_variance(runs: list[JudgeRun]) -> dict[str, float]:
    if not runs:
        return {}
    dims: set[str] = set()
    for run in runs:
        dims.update(run.dimensions.keys())
    variance: dict[str, float] = {}
    for dim in dims:
        values = [r.dimensions.get(dim, 0.0) for r in runs]
        variance[dim] = pstdev(values) if len(values) > 1 else 0.0
    return variance


def run_judge_variance(
    trace: Trace,
    n: int,
    refresh: bool,
    threshold: float,
    live_runner: LiveRunner | None = None,
    api_key: str | None = None,
) -> dict[str, object]:
    if refresh:
        if api_key is None or api_key == "":
            raise MissingApiKeyError("ANTHROPIC_API_KEY required for live refresh")
        if live_runner is None:
            raise MissingApiKeyError("live_runner must be provided for refresh")
        final_event = next(
            (e for e in trace.events if isinstance(e, FinalOutputEvent)), None,
        )
        output = final_event.output_text if final_event else ""
        runs = live_runner(output, n)
        source = "live"
    else:
        runs = list(trace.judge_runs)
        source = "cached"
    variance = compute_variance(runs)
    exceeded = sorted([dim for dim, v in variance.items() if v > threshold])
    return {
        "variance": variance,
        "threshold_exceeded": exceeded,
        "n": len(runs),
        "source": source,
    }
