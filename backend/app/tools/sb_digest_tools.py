"""Second-Brain digest tool handlers.

Each function returns a JSON-serializable dict. When the KB is disabled,
each handler returns ``{"ok": False, "error": "second_brain_disabled"}``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from datetime import date as date_t
from pathlib import Path
from typing import Any

from app import config


def _disabled(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": "second_brain_disabled"}
    if extra:
        out.update(extra)
    return out


def _cfg() -> Any:
    from second_brain.config import Config

    return Config.load()


def _parse_date(raw: str | None) -> date_t:
    if not raw:
        return date_t.today()
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _entries_for(cfg: Any, day: date_t) -> list[dict[str, Any]]:
    sidecar = cfg.digests_dir / f"{day.isoformat()}.actions.jsonl"
    if not sidecar.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in sidecar.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _applied_ids(cfg: Any, day: date_t) -> set[str]:
    path = cfg.digests_dir / f"{day.isoformat()}.applied.jsonl"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for ln in path.read_text().splitlines():
        try:
            ids.add(json.loads(ln).get("id", ""))
        except json.JSONDecodeError:
            continue
    ids.discard("")
    return ids


def _shape_entries(entries: list[dict[str, Any]], applied: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": e.get("id", ""),
            "section": e.get("section", ""),
            "line": e.get("action", {}).get("rationale")
            or e.get("action", {}).get("action", ""),
            "action": e.get("action", {}).get("action", ""),
            "applied": e.get("id") in applied,
        }
        for e in entries
    ]


def sb_digest_today(_args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    cfg = _cfg()
    today = date_t.today()
    entries = _entries_for(cfg, today)
    applied = _applied_ids(cfg, today)
    shaped = _shape_entries(entries, applied)
    unread = sum(1 for s in shaped if not s["applied"])
    return {
        "ok": True,
        "date": today.isoformat(),
        "entry_count": len(shaped),
        "unread": unread,
        "entries": shaped,
    }


def sb_digest_list(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled({"digests": []})
    limit = int(args.get("limit", 10))
    cfg = _cfg()
    digests_dir: Path = cfg.digests_dir
    if not digests_dir.exists():
        return {"ok": True, "digests": []}
    read_marks_path = digests_dir / ".read_marks"
    read_marks: set[str] = set()
    if read_marks_path.exists():
        read_marks = {
            ln.strip()
            for ln in read_marks_path.read_text().splitlines()
            if ln.strip()
        }
    rows: list[dict[str, Any]] = []
    for md in sorted(digests_dir.glob("????-??-??.md"), reverse=True):
        day_str = md.stem
        try:
            day = _parse_date(day_str)
        except ValueError:
            continue
        entries = _entries_for(cfg, day)
        applied = _applied_ids(cfg, day)
        rows.append(
            {
                "date": day_str,
                "entry_count": len(entries),
                "applied_count": len(applied),
                "read": day_str in read_marks,
            }
        )
        if len(rows) >= limit:
            break
    return {"ok": True, "digests": rows}


def sb_digest_show(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    date_str = str(args.get("date", "")).strip()
    if not date_str:
        return {"ok": False, "error": "missing date"}
    cfg = _cfg()
    md_path = cfg.digests_dir / f"{date_str}.md"
    if not md_path.exists():
        return {"ok": False, "error": "digest_not_found", "date": date_str}
    day = _parse_date(date_str)
    entries = _entries_for(cfg, day)
    applied = _applied_ids(cfg, day)
    shaped = [
        {**s, "skipped": False}
        for s in _shape_entries(entries, applied)
    ]
    return {
        "ok": True,
        "date": date_str,
        "markdown": md_path.read_text(),
        "entries": shaped,
    }


def _load_applier() -> Any:  # seam for tests
    from second_brain.digest.applier import DigestApplier

    return DigestApplier


_DigestApplier = None  # late-bound; tests may monkeypatch


def sb_digest_apply(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    raw_ids = args.get("ids")
    if raw_ids != "all" and not (isinstance(raw_ids, list) and raw_ids):
        return {"ok": False, "error": "ids required (list or 'all')"}
    date_str = args.get("date")
    day = _parse_date(date_str) if date_str else date_t.today()
    cfg = _cfg()
    if raw_ids == "all":
        ids = [e.get("id", "") for e in _entries_for(cfg, day)]
        ids = [i for i in ids if i]
    else:
        ids = [str(x) for x in raw_ids]
    applier_cls = _DigestApplier or _load_applier()
    result = applier_cls(cfg).apply(digest_date=day, entry_ids=ids)
    return {
        "ok": True,
        "applied": list(result.applied),
        "skipped": list(result.skipped),
        "failed": list(result.failed),
    }


def _load_skip_registry() -> Any:
    from second_brain.digest.skip import SkipRegistry

    return SkipRegistry


_SkipRegistry = None  # late-bound; tests may monkeypatch


def _read_skip_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def sb_digest_skip(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    entry_id = str(args.get("id", "")).strip()
    if not entry_id:
        return {"ok": False, "error": "id required"}
    ttl = int(args.get("ttl_days", 30))
    day = _parse_date(args.get("date"))
    cfg = _cfg()
    registry_cls = _SkipRegistry or _load_skip_registry()
    registry = registry_cls(cfg)
    before = _read_skip_map(registry.path)
    ok = registry.skip_by_id(digest_date=day, entry_id=entry_id, ttl_days=ttl)
    if not ok:
        return {"ok": False, "error": "entry_not_found", "id": entry_id}
    after = _read_skip_map(registry.path)
    new_sigs = {k: v for k, v in after.items() if k not in before}
    if new_sigs:
        sig, expires = next(iter(new_sigs.items()))
    else:
        # Entry already skipped earlier — surface the preserved value if we can.
        sig, expires = "", ""
    return {
        "ok": True,
        "skipped": True,
        "signature": sig,
        "expires_at": expires,
    }


_VALID_ACTIONS = frozenset(
    {
        "upgrade_confidence",
        "resolve_contradiction",
        "promote_wiki_to_claim",
        "backlink_claim_to_wiki",
        "add_taxonomy_root",
        "re_abstract_batch",
        "drop_edge",
        "keep",
    }
)


def sb_digest_propose(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    section = str(args.get("section", "")).strip()
    action = args.get("action")
    if not section:
        return {"ok": False, "error": "section required"}
    if not isinstance(action, dict) or action.get("action") not in _VALID_ACTIONS:
        return {"ok": False, "error": "invalid_action_type"}
    cfg = _cfg()
    pending = cfg.digests_dir / "pending.jsonl"
    pending.parent.mkdir(parents=True, exist_ok=True)
    existing = pending.read_text().splitlines() if pending.exists() else []
    pending_id = f"pend_{len(existing) + 1:04d}"
    record = {
        "id": pending_id,
        "section": section,
        "action": action,
        "proposed_at": datetime.now(UTC).isoformat(),
    }
    with pending.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"ok": True, "pending_id": pending_id, "file": str(pending)}


def _collect_stats(cfg: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from dataclasses import asdict

    from second_brain.stats.collector import collect_stats
    from second_brain.stats.health import compute_health

    stats = collect_stats(cfg)
    health = compute_health(stats)
    return asdict(stats), asdict(health)


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    try:
        from dataclasses import asdict, is_dataclass

        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
    except Exception:  # noqa: BLE001
        pass
    return dict(getattr(obj, "__dict__", {}))


def sb_stats(_args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    cfg = _cfg()
    stats, health = _collect_stats(cfg)
    return {
        "ok": True,
        "stats": _as_dict(stats),
        "health": _as_dict(health),
    }
