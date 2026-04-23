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

import json
from pathlib import Path
from typing import Any

from second_brain.digest.schema import DigestEntry


def _pending_path(cfg) -> Path:
    return cfg.digests_dir / "pending.jsonl"


def read_pending(cfg) -> list[DigestEntry]:
    """Return proposals from ``digests/pending.jsonl`` without mutating the file.

    Malformed lines are skipped silently to avoid blocking a build on a single
    bad record. Returns an empty list if the pending file does not exist.
    """
    pending = _pending_path(cfg)
    if not pending.exists():
        return []

    out: list[DigestEntry] = []
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
        digest_line = action.get("rationale") or action.get("action", "")
        out.append(
            DigestEntry(
                id=str(record.get("id", "")),
                section=str(record.get("section", "")),
                line=str(digest_line),
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
