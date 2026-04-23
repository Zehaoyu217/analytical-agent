from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from second_brain.config import Config


class EventKind(StrEnum):
    AUTO = "AUTO"
    USER_OVERRIDE = "USER_OVERRIDE"
    SUGGEST = "SUGGEST"
    INGEST = "INGEST"
    REINDEX = "REINDEX"
    ERROR = "ERROR"
    RETRY = "RETRY"
    WATCH = "WATCH"
    MAINTAIN = "MAINTAIN"


def append_event(
    *,
    kind: EventKind,
    op: str,
    subject: str,
    value: str,
    reason: dict[str, Any] | None = None,
    home: Path | None = None,
) -> None:
    cfg = Config.load() if home is None else None
    log_path = (home / "log.md") if home else cfg.log_path  # type: ignore[union-attr]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"- {ts} [{kind}] {op} {subject} → {value}"
    if reason:
        line += f"\n  reason: {json.dumps(reason, separators=(',', ':'))}"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
