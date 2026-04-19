from __future__ import annotations

import time
from pathlib import Path

from app.wiki.schema import Finding

MAX_WORKING_LINES = 200

# log.md is append-only; trim when it exceeds this threshold.
_LOG_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def _trim_log_to_size(content: str, max_bytes: int) -> str:
    """Drop the oldest log entries until *content* fits within *max_bytes*.

    The ``# Log`` header block (all leading ``#``-lines and blank lines) is
    always preserved.  Entries are lines that start with ``- ``; anything that
    doesn't match is treated as a header continuation and kept too.

    O(n) implementation: accumulates byte sizes with a running total and finds
    the first body index to keep in a single forward pass, then slices once.
    """
    lines = content.splitlines(keepends=True)

    # Split into header block (lines starting with '#' or blank) and body.
    header: list[str] = []
    body: list[str] = []
    in_header = True
    for line in lines:
        stripped = line.strip()
        if in_header and (not stripped or stripped.startswith("#")):
            header.append(line)
        else:
            in_header = False
            body.append(line)

    header_bytes = len("".join(header).encode("utf-8"))
    body_sizes = [len(line.encode("utf-8")) for line in body]
    total = header_bytes + sum(body_sizes)

    if total <= max_bytes:
        return content  # nothing to drop

    # Walk forward, subtracting the oldest line each step, until we fit.
    drop_until = 0
    while drop_until < len(body) and total > max_bytes:
        total -= body_sizes[drop_until]
        drop_until += 1

    return "".join(header) + "".join(body[drop_until:])


class WikiEngine:
    def __init__(self, root: Path) -> None:
        self.root = root
        # Throttle session cleanup to at most once per hour — scanning the
        # sessions directory on every write is unnecessary when files are few.
        self._last_cleanup_ts: float = 0.0

    # ── working.md ──────────────────────────────────────────────────────────

    def read_working(self) -> str:
        return (self.root / "working.md").read_text()

    def write_working(self, content: str) -> None:
        lines = content.splitlines()
        if len(lines) > MAX_WORKING_LINES:
            raise ValueError(
                f"working.md exceeds {MAX_WORKING_LINES} lines ({len(lines)}); compact first"
            )
        (self.root / "working.md").write_text(content)

    # ── log.md ──────────────────────────────────────────────────────────────

    def append_log(self, line: str) -> None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = self.root / "log.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else "# Log\n\n"
        new_content = existing + f"- {stamp} — {line}\n"
        if len(new_content.encode("utf-8")) > _LOG_MAX_BYTES:
            new_content = _trim_log_to_size(new_content, _LOG_MAX_BYTES)
        path.write_text(new_content, encoding="utf-8")

    # ── findings ────────────────────────────────────────────────────────────

    def promote_finding(self, finding: Finding) -> Path:
        if not finding.evidence:
            raise ValueError("cannot promote finding without evidence (need artifact IDs)")
        if not finding.stat_validate_pass:
            raise ValueError("cannot promote finding without stat_validate PASS")
        body = (
            f"# {finding.title}\n\n"
            f"**Finding ID:** `{finding.id}`\n\n"
            f"## Summary\n\n{finding.body}\n\n"
            f"## Evidence\n\n"
            + "\n".join(f"- `{a}`" for a in finding.evidence)
            + "\n"
        )
        path = self.root / "findings" / f"{finding.id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    # ── index ───────────────────────────────────────────────────────────────

    def _list_titles(self, subdir: str) -> list[tuple[str, str]]:
        folder = self.root / subdir
        if not folder.exists():
            return []
        out: list[tuple[str, str]] = []
        for md in sorted(folder.glob("*.md")):
            first_heading = next(
                (
                    ln.lstrip("# ").strip()
                    for ln in md.read_text().splitlines()
                    if ln.startswith("# ")
                ),
                md.stem,
            )
            out.append((md.stem, first_heading))
        return out

    def rebuild_index(self) -> None:
        sections = [
            ("Findings", self._list_titles("findings")),
            ("Hypotheses", self._list_titles("hypotheses")),
            ("Entities", self._list_titles("entities")),
            ("Meta", self._list_titles("meta")),
        ]
        lines = ["# Wiki Index", ""]
        for heading, items in sections:
            lines.append(f"## {heading}")
            lines.append("")
            if not items:
                lines.append("_(no pages yet)_")
            else:
                for stem, title in items:
                    lines.append(f"- [{stem}]({stem}.md) — {title}")
            lines.append("")
        (self.root / "index.md").write_text("\n".join(lines))

    # ── session notes (P18) ──────────────────────────────────────────────────

    def write_session_notes(self, session_id: str, notes: str) -> Path:
        """Write the structured session notes for a session and prune stale files.

        Overwrites on every turn so the file always reflects the latest
        turn's summary (log.md handles the chronological record).

        After writing, any session files older than 3 days are deleted
        automatically to prevent unbounded accumulation.
        """
        safe_id = _safe_session_filename(session_id)
        folder = self.root / "sessions"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{safe_id}.md"
        path.write_text(notes)
        # Only scan the sessions directory at most once per hour to avoid
        # redundant filesystem work on every turn.
        cleanup_interval = 3600.0
        if time.time() - self._last_cleanup_ts >= cleanup_interval:
            self.cleanup_old_sessions(max_age_days=3)
            self._last_cleanup_ts = time.time()
        return path

    def latest_session_notes(self, exclude_session_id: str = "") -> str:
        """Return the most-recently-modified session notes, or '' if none exist.

        ``exclude_session_id`` skips the current session so we don't inject
        a session's own notes back into itself mid-run.
        """
        folder = self.root / "sessions"
        if not folder.exists():
            return ""
        exclude_stem = _safe_session_filename(exclude_session_id) if exclude_session_id else ""
        candidates = [
            f for f in folder.glob("*.md")
            if f.stem != exclude_stem
        ]
        if not candidates:
            return ""
        latest = max(candidates, key=lambda f: f.stat().st_mtime)
        return latest.read_text(encoding="utf-8")

    def cleanup_old_sessions(self, max_age_days: int = 3) -> int:
        """Delete session note files older than *max_age_days*. Returns count deleted."""
        folder = self.root / "sessions"
        if not folder.exists():
            return 0
        cutoff = time.time() - max_age_days * 86_400
        deleted = 0
        for f in folder.glob("*.md"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    deleted += 1
            except OSError:
                pass  # already gone or permission issue — skip silently
        return deleted


def _safe_session_filename(session_id: str) -> str:
    """Reduce a session id to a safe filename (alnum/-/_)."""
    if not session_id:
        return "unknown"
    cleaned = "".join(c if (c.isalnum() or c in "-_") else "-" for c in session_id)
    return cleaned[:96] or "unknown"
