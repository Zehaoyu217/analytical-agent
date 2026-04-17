"""Diff and IssueRef dataclasses — the core unit of autofix proposals.

Diff is full-file replacement (not unified-diff hunks): every fix class
regenerates a small file or makes a localized edit to a single file. Full-content
snapshots make staleness detection trivial (`current_text != original_content`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IssueRef:
    """Reference to an integrity issue this diff resolves."""

    plugin: str
    rule: str
    message: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class Diff:
    """Full-file replacement proposal.

    `path` is relative to repo_root.
    `original_content` is "" when creating a new file.
    """

    path: Path
    original_content: str
    new_content: str
    rationale: str
    source_issues: tuple[IssueRef, ...]

    def __post_init__(self) -> None:
        if self.path.is_absolute():
            raise ValueError(f"Diff.path must be relative, got {self.path}")

    def is_noop(self) -> bool:
        return self.original_content == self.new_content

    def stale_against(self, repo_root: Path) -> bool:
        """True if `path` on disk no longer matches `original_content`."""
        target = repo_root / self.path
        if not target.exists():
            return self.original_content != ""
        return target.read_text() != self.original_content
