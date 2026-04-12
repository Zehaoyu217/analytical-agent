"""Read-only store: list summaries and load full traces from disk."""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.trace.events import Trace, TraceSummary

_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class TraceNotFoundError(FileNotFoundError):
    pass


def _validate_trace_id(trace_id: str) -> None:
    if not _TRACE_ID_RE.match(trace_id):
        raise ValueError("invalid trace_id")


def list_traces(traces_dir: Path) -> list[TraceSummary]:
    if not traces_dir.exists():
        return []
    summaries: list[TraceSummary] = []
    for path in sorted(traces_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(raw, dict):
            continue
        summary_raw = raw.get("summary")
        if not isinstance(summary_raw, dict):
            continue
        try:
            summaries.append(TraceSummary.model_validate(summary_raw))
        except ValidationError:
            continue
    return summaries


def load_trace(traces_dir: Path, trace_id: str) -> Trace:
    _validate_trace_id(trace_id)
    path = traces_dir / f"{trace_id}.yaml"
    if not path.exists():
        raise TraceNotFoundError(f"trace not found: {trace_id}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"corrupted trace YAML: {trace_id}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"invalid trace structure: {trace_id}")
    try:
        return Trace.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"trace failed schema validation: {trace_id}") from exc
