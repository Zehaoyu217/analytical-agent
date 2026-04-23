"""Gardener audit log — append-only JSONL at ``.sb/.state/gardener.log.jsonl``.

Every proposal the gardener emits gets one row. Digest flips ``accepted``
when it emits (or skips) the proposal, so the audit doubles as a
proposal → outcome trail.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def audit_path(cfg: Any) -> Path:
    return Path(cfg.sb_dir) / ".state" / "gardener.log.jsonl"


def append(cfg: Any, entry: dict[str, Any]) -> None:
    path = audit_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def tail(
    cfg: Any, n: int = 50, filter_pass: str | None = None
) -> list[dict[str, Any]]:
    path = audit_path(cfg)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if filter_pass and row.get("pass") != filter_pass:
                continue
            rows.append(row)
    return rows[-n:]


def mark_accepted(cfg: Any, match_line: str, accepted: bool) -> int:
    """Flip ``accepted`` on rows whose ``line`` matches. Returns count updated.

    Rewrites the whole file — acceptable because audits are bounded
    (per-run) and we rarely need to flip. If the file grows past ~10MB
    we'll want a sidecar index, but that's out of scope here.
    """
    path = audit_path(cfg)
    if not path.exists():
        return 0
    updated = 0
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if row.get("line") == match_line and row.get("accepted") is None:
                row["accepted"] = accepted
                updated += 1
            rows.append(row)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return updated
