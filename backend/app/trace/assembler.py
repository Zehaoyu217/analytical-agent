"""Prompt assembler: reads captured sections, detects byte-range conflicts."""
from __future__ import annotations

import re

from app.trace.events import LlmCallEvent, PromptSection, Trace

_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")


class StepNotFoundError(LookupError):
    pass


def _parse_range(spec: str) -> tuple[int, int] | None:
    match = _RANGE_RE.match(spec.strip())
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        return None
    return start, end


def detect_conflicts(sections: list[PromptSection]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for i, a in enumerate(sections):
        range_a = _parse_range(a.lines)
        if range_a is None:
            continue
        for b in sections[i + 1:]:
            if a.source != b.source:
                continue
            range_b = _parse_range(b.lines)
            if range_b is None:
                continue
            overlap_start = max(range_a[0], range_b[0])
            overlap_end = min(range_a[1], range_b[1])
            if overlap_start <= overlap_end:
                conflicts.append({
                    "source_a": a.source,
                    "source_b": b.source,
                    "overlap": f"{overlap_start}-{overlap_end}",
                })
    return conflicts


def assemble_prompt(trace: Trace, step_id: str) -> dict[str, object]:
    for event in trace.events:
        if isinstance(event, LlmCallEvent) and event.step_id == step_id:
            return {
                "sections": [s.model_dump() for s in event.sections],
                "conflicts": detect_conflicts(list(event.sections)),
            }
    raise StepNotFoundError(f"step_id not in trace: {step_id}")
