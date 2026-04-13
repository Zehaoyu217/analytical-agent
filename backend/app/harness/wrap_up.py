from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from app.harness.turn_state import TurnState

FINDING_RE = re.compile(
    r"^(?P<id>\[F-\d{8}-\d{3}\])\s+(?P<body>.+?)\."
    r"(?:\s+Evidence:\s*(?P<evidence>[^\.\n]+?)\.)?"
    r"(?:\s+Validated:\s*(?P<validated>[^\.\n]+?)\.)?\s*$",
    re.MULTILINE,
)


class _Wiki(Protocol):
    def append_log(self, entry: str) -> None: ...
    def update_working(self, content: str) -> None: ...
    def rebuild_index(self) -> None: ...
    def promote_finding(
        self, *, finding_id: str, body: str,
        evidence_ids: list[str], validated_by: str,
    ) -> None: ...


class _Bus(Protocol):
    def emit(self, event: dict) -> None: ...


@dataclass(frozen=True, slots=True)
class WrapUpResult:
    promoted_finding_ids: tuple[str, ...] = field(default_factory=tuple)
    appended_log: bool = True


def _parse_findings(scratchpad: str) -> list[dict]:
    # Only scan lines inside the "## Findings" section if present.
    lines = scratchpad.splitlines()
    start, end = None, None
    for i, line in enumerate(lines):
        if line.strip() == "## Findings":
            start = i + 1
        elif start is not None and line.startswith("## ") and i > start:
            end = i
            break
    if start is None:
        return []
    section = "\n".join(lines[start:end if end else None])
    findings: list[dict] = []
    for m in FINDING_RE.finditer(section):
        fid = m.group("id").strip("[]")
        body = m.group("body").strip()
        ev_raw = (m.group("evidence") or "").strip()
        val = (m.group("validated") or "").strip()
        ev = [e.strip() for e in re.split(r"[,\s]+", ev_raw) if e.strip()]
        findings.append({
            "id": fid,
            "body": body,
            "evidence_ids": ev,
            "validated_by": val,
        })
    return findings


def _validate_passed(state: TurnState) -> bool:
    for evt in state.as_trace():
        if evt.get("tool") == "stat_validate.validate":
            result = evt.get("result") or {}
            if str(result.get("status", "")).upper() == "PASS":
                return True
    return False


class TurnWrapUp:
    def __init__(self, wiki: _Wiki, event_bus: _Bus) -> None:
        self._wiki = wiki
        self._bus = event_bus

    def finalize(
        self,
        state: TurnState,
        final_text: str,
        session_id: str,
        turn_index: int,
    ) -> WrapUpResult:
        promoted: list[str] = []
        parse_ok = _validate_passed(state)
        for f in _parse_findings(state.scratchpad):
            if not f["evidence_ids"] or not f["validated_by"] or not parse_ok:
                continue
            self._wiki.promote_finding(
                finding_id=f["id"], body=f["body"],
                evidence_ids=list(f["evidence_ids"]),
                validated_by=f["validated_by"],
            )
            promoted.append(f["id"])

        self._wiki.update_working(state.scratchpad)
        self._wiki.rebuild_index()
        self._wiki.append_log(
            f"turn {turn_index}: session={session_id} "
            f"artifacts={list(state.artifact_ids())} promoted={promoted}"
        )
        self._bus.emit({
            "type": "turn_completed",
            "session_id": session_id,
            "turn_index": turn_index,
            "artifact_ids": list(state.artifact_ids()),
            "promoted_finding_ids": promoted,
            "final_text_preview": final_text[:200],
        })
        return WrapUpResult(
            promoted_finding_ids=tuple(promoted),
            appended_log=True,
        )
