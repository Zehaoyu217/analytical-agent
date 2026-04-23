"""Pure digest renderers — markdown + actions.jsonl.

No I/O. The Builder writes the returned strings to disk.
"""

from __future__ import annotations

import json
from datetime import date

from second_brain.digest.schema import DigestEntry

# Fixed section order — matches the pass prefix order in DigestBuilder.
_SECTION_ORDER: tuple[str, ...] = (
    "Reconciliation",
    "Wiki ↔ KB drift",
    "Taxonomy drift",
    "Stale review",
    "Edge audit",
)


def _group_by_section(entries: list[DigestEntry]) -> dict[str, list[DigestEntry]]:
    groups: dict[str, list[DigestEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.section, []).append(entry)
    return groups


def render_markdown(d: date, entries: list[DigestEntry]) -> str:
    """Render a ``# Digest YYYY-MM-DD`` markdown document from ordered entries."""
    if not entries:
        return f"# Digest {d.isoformat()}\n"
    groups = _group_by_section(entries)
    lines: list[str] = [f"# Digest {d.isoformat()}", ""]
    # Fixed order first, then any extra sections alphabetically.
    ordered = [s for s in _SECTION_ORDER if s in groups]
    extras = sorted(s for s in groups if s not in _SECTION_ORDER)
    for section in ordered + extras:
        lines.append(f"## {section}")
        for entry in groups[section]:
            lines.append(f"- [{entry.id}] {entry.line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_actions_jsonl(entries: list[DigestEntry]) -> str:
    """One ``{"id": ..., "action": {...}}`` JSON object per line."""
    if not entries:
        return ""
    out = [
        json.dumps({"id": e.id, "section": e.section, "action": e.action}, sort_keys=True)
        for e in entries
    ]
    return "\n".join(out) + "\n"
