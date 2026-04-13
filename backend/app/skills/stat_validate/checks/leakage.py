from __future__ import annotations

from datetime import datetime

from app.skills.stat_validate.verdict import Violation


def _parse(ts: str | datetime) -> datetime | None:
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts))
    except ValueError:
        return None


def check_leakage(payload: dict) -> Violation | None:
    as_of = payload.get("as_of")
    max_ts = payload.get("feature_timestamps_max")
    if as_of is None or max_ts is None:
        return None
    a = _parse(as_of)
    m = _parse(max_ts)
    if a is None or m is None:
        return None
    if m > a:
        return Violation(
            code="look_ahead_leakage",
            severity="WARN",
            message=f"feature max ts {m.isoformat()} > as_of {a.isoformat()}",
            gotcha_refs=("look_ahead_bias",),
        )
    return None
