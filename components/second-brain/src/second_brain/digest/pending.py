"""Merge agent-proposed digest entries from ``digests/pending.jsonl``.

External agents (e.g. the claude-code-agent bridge) can append proposals to
``digests/pending.jsonl`` via an ``sb_digest_propose`` tool. The next
``DigestBuilder.build`` call absorbs those proposals into the build so they
become first-class digest entries.

Two-phase design: ``read_pending`` returns the parsed proposals without
mutating the file, and ``truncate_pending`` is called only after the build is
guaranteed to emit. This prevents the "empty digest + truncated pending" race
that would silently drop a proposal when passes return too few entries to
satisfy ``min_entries_to_emit``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from second_brain.digest.schema import DigestEntry


def _pending_path(cfg) -> Path:
    return cfg.digests_dir / "pending.jsonl"


def _extract_line(action: dict[str, Any]) -> str:
    """Pick the human-readable line from an action's fields.

    Different producers write different action shapes:
    - Gardener extract: ``action.statement`` holds the claim text
    - Legacy agent proposer: ``action.rationale`` or ``action.action``
    - Fallback: action ``type`` so the UI never renders ``- [] ``.
    """
    for key in ("statement", "rationale", "action", "title", "summary"):
        val = action.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return str(action.get("type", "")) or ""


def _synth_id(action: dict[str, Any], counter: int) -> str:
    """Synthesize a stable id for a proposal that didn't ship one.

    The digest applier keys off ``entry.id`` — an empty id means the user
    can't individually accept/skip the proposal. We derive an id from the
    action's key fields so the same input produces the same id across runs.
    """
    seed = json.dumps(action, sort_keys=True)
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
    return f"ex{counter:02d}-{digest}"


def read_pending(cfg) -> list[DigestEntry]:
    """Return proposals from ``digests/pending.jsonl`` without mutating the file.

    Malformed lines are skipped silently to avoid blocking a build on a single
    bad record. Returns an empty list if the pending file does not exist.
    """
    pending = _pending_path(cfg)
    if not pending.exists():
        return []

    out: list[DigestEntry] = []
    counter = 0
    for raw_line in pending.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            record: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        action = record.get("action") or {}
        if not isinstance(action, dict):
            action = {}
        counter += 1
        entry_id = str(record.get("id", "")).strip() or _synth_id(action, counter)
        out.append(
            DigestEntry(
                id=entry_id,
                section=str(record.get("section", "")),
                line=_extract_line(action),
                action=action,
            )
        )
    return out


def truncate_pending(cfg) -> None:
    """Clear ``digests/pending.jsonl``. Safe to call when the file is absent."""
    pending = _pending_path(cfg)
    if pending.exists():
        pending.write_text("")


def merge_pending(cfg, existing: list[DigestEntry]) -> list[DigestEntry]:
    """Append proposals from ``digests/pending.jsonl`` to ``existing``.

    **Deprecated for new callers** — destructive (truncates the file). Prefer
    :func:`read_pending` + :func:`truncate_pending` so the file is only cleared
    after a successful emit. Kept for backward compatibility with any external
    caller that relied on the original one-shot semantics.
    """
    proposals = read_pending(cfg)
    truncate_pending(cfg)
    return list(existing) + proposals
