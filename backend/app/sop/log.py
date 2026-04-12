"""Read/write iteration log entries."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.sop.types import IterationLogEntry


def _entry_path(session_id: str, log_dir: Path) -> Path:
    return log_dir / f"{session_id}.yaml"


def write_entry(entry: IterationLogEntry, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = _entry_path(entry.session_id, log_dir)
    path.write_text(yaml.safe_dump(entry.model_dump(), sort_keys=False))
    return path


def read_entry(session_id: str, log_dir: Path) -> IterationLogEntry:
    path = _entry_path(session_id, log_dir)
    if not path.exists():
        raise FileNotFoundError(f"No log entry at {path}")
    data = yaml.safe_load(path.read_text())
    return IterationLogEntry.model_validate(data)


def list_entries(log_dir: Path) -> list[IterationLogEntry]:
    if not log_dir.exists():
        return []
    entries = []
    for path in sorted(log_dir.glob("*.yaml")):
        entries.append(IterationLogEntry.model_validate(yaml.safe_load(path.read_text())))
    return entries


def next_session_id(log_dir: Path, level: int, date: str) -> str:
    prefix = f"{date}-level{level}-"
    if not log_dir.exists():
        return f"{prefix}001"
    existing = sorted(
        int(p.stem.rsplit("-", 1)[1])
        for p in log_dir.glob(f"{prefix}*.yaml")
    )
    n = (existing[-1] + 1) if existing else 1
    return f"{prefix}{n:03d}"
