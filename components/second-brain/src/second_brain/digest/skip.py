"""Digest skip registry — TTL-backed JSON file at ``.sb/digest_skips.json``.

A *skip* records that the user has dismissed a given digest entry; the next
``DigestBuilder`` run filters it out until the TTL expires.

Signatures are a stable hash of the entry's section + action name + primary
target (claim_id / target_id / root / wiki_path / src_id, in that preference
order). This way, the same suggestion for the same subject reproduces the same
signature tomorrow even if its line wording changes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry

_PRIMARY_KEYS: tuple[str, ...] = (
    "claim_id",
    "left_id",
    "src_id",
    "target_id",
    "root",
    "wiki_path",
    "taxonomy",
)


def _primary_target(action: dict[str, Any]) -> str:
    for key in _PRIMARY_KEYS:
        v = action.get(key)
        if isinstance(v, str) and v:
            return v
    # Fallback: batched re_abstract_batch ⇒ first claim id.
    cids = action.get("claim_ids")
    if isinstance(cids, list) and cids:
        first = cids[0]
        if isinstance(first, str):
            return first
    return ""


class SkipRegistry:
    """Reads/writes ``.sb/digest_skips.json`` — ``{signature: expires_iso_date}``."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.path = cfg.sb_dir / "digest_skips.json"

    # ---- signatures -------------------------------------------------------

    def signature(self, entry: DigestEntry) -> str:
        action = entry.action
        action_name = str(action.get("action", ""))
        target = _primary_target(action)
        raw = f"{entry.section}|{action_name}|{target}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ---- storage ----------------------------------------------------------

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}

    def _save(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    # ---- public API -------------------------------------------------------

    def skip(self, entry: DigestEntry, *, today: date, ttl_days: int) -> None:
        self.skip_signature(self.signature(entry), today=today, ttl_days=ttl_days)

    def skip_signature(self, sig: str, *, today: date, ttl_days: int) -> None:
        data = self._load()
        expires = today + timedelta(days=max(0, ttl_days))
        data[sig] = expires.isoformat()
        self._save(data)

    def is_skipped(self, entry: DigestEntry, *, today: date) -> bool:
        """Purges expired entries as a side effect before checking."""
        data = self._load()
        changed = False
        alive: dict[str, str] = {}
        for sig, exp_iso in data.items():
            try:
                exp = date.fromisoformat(exp_iso)
            except ValueError:
                changed = True
                continue
            if exp < today:
                changed = True
                continue
            alive[sig] = exp_iso
        if changed:
            self._save(alive)
        return self.signature(entry) in alive

    def skip_by_id(
        self,
        *,
        digest_date: date,
        entry_id: str,
        today: date | None = None,
        ttl_days: int = 14,
    ) -> bool:
        """Look up ``entry_id`` in the sidecar actions.jsonl for ``digest_date`` and skip it.

        Returns ``True`` when the entry was found and recorded; ``False`` when
        the id is not present in that day's digest.
        """
        today = today or datetime.now().date()
        sidecar = self.cfg.digests_dir / f"{digest_date.isoformat()}.actions.jsonl"
        if not sidecar.exists():
            return False
        for line in sidecar.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("id") != entry_id:
                continue
            action = row.get("action", {})
            section = row.get("section", "")
            if not isinstance(action, dict) or not isinstance(section, str):
                return False
            synthetic = DigestEntry(id=entry_id, section=section, line="", action=action)
            self.skip_signature(self.signature(synthetic), today=today, ttl_days=ttl_days)
            return True
        return False
