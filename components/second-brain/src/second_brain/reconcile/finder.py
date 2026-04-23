from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.habits import Habits


@dataclass(frozen=True)
class OpenDebate:
    left_id: str
    right_id: str
    left_path: str
    right_path: str


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            # Accept the Z suffix shorthand.
            s = value.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def find_open_debates(cfg: Config, habits: Habits) -> list[OpenDebate]:
    if not cfg.claims_dir.exists():
        return []
    grace = timedelta(days=habits.conflicts.grace_period_days)
    cutoff = datetime.now(UTC) - grace

    # Map id → (path, meta).
    claims: dict[str, tuple[str, dict]] = {}
    for p in cfg.claims_dir.glob("*.md"):
        if p.parent.name == "resolutions":
            continue
        meta, _ = load_document(p)
        cid = str(meta.get("id") or "")
        if cid:
            claims[cid] = (str(p), meta)

    debates: list[OpenDebate] = []
    seen: set[tuple[str, str]] = set()

    for cid, (path, meta) in claims.items():
        if meta.get("resolution"):
            continue
        extracted = _parse_dt(meta.get("extracted_at"))
        if extracted is None or extracted > cutoff:
            continue
        for other_id in meta.get("contradicts") or []:
            other = claims.get(other_id)
            if other is None:
                continue
            # Canonicalize the pair by sorted id so we don't emit duplicates.
            left, right = sorted((cid, other_id))
            if (left, right) in seen:
                continue
            seen.add((left, right))
            left_path, _ = claims[left]
            right_path, _ = claims[right]
            debates.append(OpenDebate(
                left_id=left, right_id=right,
                left_path=left_path, right_path=right_path,
            ))
    return debates
