"""Pre-turn hook: summarize today's Second-Brain digest.

Returns a short string to inject into the system prompt, or ``None``.
The hook is intentionally defensive — it must never raise and must never
break a turn. Any exception is logged and swallowed.

Gating:
- Returns ``None`` when ``SECOND_BRAIN_ENABLED`` is falsy.
- Returns ``None`` when ``SB_DIGEST_HOOK_ENABLED`` env is ``0``/``false``/``no``.
- Returns ``None`` when today's digest sidecar is missing.
- Returns ``None`` when today's date is present in ``digests/.read_marks``.
- Returns ``None`` when every entry has already been applied.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import date as date_t
from pathlib import Path
from typing import Any

from app import config as app_config

logger = logging.getLogger(__name__)

_DISABLED_VALUES = frozenset({"0", "false", "no"})


def _load_config() -> Any:  # late-bound seam for tests
    from second_brain.config import Config

    return Config.load()


def _read_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.add(json.loads(ln).get("id", ""))
        except json.JSONDecodeError:
            continue
    out.discard("")
    return out


def _read_marks(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text().splitlines() if ln.strip()}


def _read_entries(sidecar: Path) -> list[dict]:
    entries: list[dict] = []
    for ln in sidecar.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            entries.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return entries


def build_digest_summary() -> str | None:
    """Return a one-paragraph summary of today's unread digest, or None.

    Purely functional: does not mutate any file.
    """
    try:
        if not getattr(app_config, "SECOND_BRAIN_ENABLED", False):
            return None
        hook_flag = os.environ.get("SB_DIGEST_HOOK_ENABLED", "true").lower()
        if hook_flag in _DISABLED_VALUES:
            return None
        cfg = _load_config()
        today = date_t.today()
        sidecar = cfg.digests_dir / f"{today.isoformat()}.actions.jsonl"
        if not sidecar.exists():
            return None
        if today.isoformat() in _read_marks(cfg.digests_dir / ".read_marks"):
            return None
        entries = _read_entries(sidecar)
        applied = _read_ids(cfg.digests_dir / f"{today.isoformat()}.applied.jsonl")
        unread = [e for e in entries if e.get("id") not in applied]
        if not unread:
            return None
        sections = Counter(e.get("section", "unknown") for e in unread)
        section_summary = ", ".join(f"{n} {s}" for s, n in sections.most_common())
        return (
            f"You have {len(unread)} pending KB decisions ({today.isoformat()}). "
            f"Tools: sb_digest_show, sb_digest_apply, sb_digest_skip.\n"
            f"Section summary: {section_summary}.\n"
            "Offer to review only if relevant to the conversation."
        )
    except Exception:  # noqa: BLE001 — hook must never break a turn
        logger.exception("sb_digest_hook failed")
        return None
