"""Fixer: rewrite broken markdown links when their rename is unambiguous.

For each `doc.broken_link` issue, runs `git log --diff-filter=R --follow`
on the broken target. If exactly one rename event is found in the lookback
window with exactly one new path, rewrites the link in the source doc.

Skips ambiguous renames silently (caller emits autofix.skipped_ambiguous_rename
INFO via the plugin layer).
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..diff import Diff, IssueRef
from ..loader import SiblingArtifacts

LOOKBACK = "365.days.ago"
RENAME_RE = re.compile(r"^---\s+a/(.+)\n\+\+\+\s+b/(.+)$", re.MULTILINE)


def _find_unique_rename(
    repo_root: Path,
    broken_target: str,
    lookback: str,
    timeout_seconds: int,
) -> str | None:
    proc = subprocess.run(
        [
            "git", "-C", str(repo_root), "log",
            "--diff-filter=R", "--follow",
            f"--since={lookback}",
            "-p", "--", broken_target,
        ],
        capture_output=True, text=True,
        timeout=timeout_seconds, check=False,
    )
    if proc.returncode != 0:
        return None
    matches = RENAME_RE.findall(proc.stdout or "")
    new_paths = {new for old, new in matches if old == broken_target}
    if len(new_paths) != 1:
        return None
    return new_paths.pop()


def propose(
    artifacts: SiblingArtifacts,
    repo_root: Path,
    config: dict[str, Any],
) -> list[Diff]:
    if not artifacts.doc_audit:
        return []
    timeout = int(config.get("git_log_timeout_seconds", 30))
    lookback = str(config.get("rename_lookback", LOOKBACK))

    issues_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for i in artifacts.doc_audit.get("issues", []):
        if i.get("rule") != "doc.broken_link":
            continue
        ev = i.get("evidence", {})
        src = ev.get("source")
        if not src:
            continue
        issues_by_source[src].append(i)

    diffs: list[Diff] = []
    for source, issues in sorted(issues_by_source.items()):
        source_path = repo_root / source
        if not source_path.exists():
            continue
        original = source_path.read_text()
        new_text = original
        refs: list[IssueRef] = []
        rewrites: list[tuple[str, str]] = []

        for issue in issues:
            ev = issue.get("evidence", {})
            old_target = ev.get("link_target")
            if not old_target:
                continue
            new_target = _find_unique_rename(
                repo_root, old_target, lookback, timeout,
            )
            if new_target is None:
                continue
            new_text = new_text.replace(f"]({old_target})", f"]({new_target})")
            rewrites.append((old_target, new_target))
            refs.append(IssueRef(
                plugin="doc_audit",
                rule="doc.broken_link",
                message=str(issue.get("message", "")),
                evidence=dict(ev),
            ))

        if new_text == original:
            continue
        rationale = (
            f"Rewrite {len(rewrites)} broken link(s) per `git log --diff-filter=R --follow`"
        )
        diffs.append(Diff(
            path=Path(source),
            original_content=original,
            new_content=new_text,
            rationale=rationale,
            source_issues=tuple(refs),
        ))

    return diffs
