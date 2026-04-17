"""Safety preflight for Plugin F autofix.

Seven refusal modes:
  1. autofix.skipped_upstream_missing  (INFO) — required sibling artifact absent
  2. autofix.skipped_upstream_failure  (INFO) — sibling artifact had a parse error
  3. apply.dirty_tree                  (ERROR) — `git status --porcelain` non-empty
  4. apply.gh_unavailable              (ERROR) — `gh` not on PATH
  5. apply.no_remote                   (ERROR) — `git remote get-url origin` fails
  6. apply.path_escape                 (ERROR) — diff resolves outside repo_root
  7. apply.stale_diff                  (ERROR) — Diff.stale_against() True (raised in dispatcher)

Auto-checkout-on-main is NOT a refusal mode; the dispatcher always creates an
autofix branch from origin/main, so being on main is harmless.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .diff import Diff
from .loader import SiblingArtifacts

REQUIRED_ARTIFACTS = ("doc_audit", "config_registry", "graph_lint", "aggregate")


@dataclass(frozen=True)
class SafetyVerdict:
    ok: bool
    rule: str = ""
    severity: Literal["INFO", "ERROR"] | None = None
    message: str = ""


def check_upstream(artifacts: SiblingArtifacts) -> SafetyVerdict:
    """Verify all required sibling artifacts loaded cleanly."""
    for name in REQUIRED_ARTIFACTS:
        failure = artifacts.failures.get(name)
        if failure is None:
            continue
        if failure == "missing":
            return SafetyVerdict(
                ok=False,
                rule="autofix.skipped_upstream_missing",
                severity="INFO",
                message=f"sibling artifact {name!r} missing — skipping all fix classes",
            )
        return SafetyVerdict(
            ok=False,
            rule="autofix.skipped_upstream_failure",
            severity="INFO",
            message=f"sibling artifact {name!r} unparseable: {failure}",
        )
    return SafetyVerdict(ok=True)


def check_apply_preflight(repo_root: Path, gh_executable: str) -> SafetyVerdict:
    """Verify it is safe to actually run git+gh side effects."""
    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if status.stdout.strip():
        return SafetyVerdict(
            ok=False,
            rule="apply.dirty_tree",
            severity="ERROR",
            message="working tree has uncommitted changes — refusing apply",
        )

    remote = subprocess.run(
        ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if remote.returncode != 0 or not remote.stdout.strip():
        return SafetyVerdict(
            ok=False,
            rule="apply.no_remote",
            severity="ERROR",
            message="no `origin` remote — refusing apply",
        )

    if shutil.which(gh_executable) is None:
        return SafetyVerdict(
            ok=False,
            rule="apply.gh_unavailable",
            severity="ERROR",
            message=f"`{gh_executable}` not on PATH — refusing apply",
        )

    return SafetyVerdict(ok=True)


def check_diff_path(diff: Diff, repo_root: Path) -> SafetyVerdict:
    """Refuse diffs whose absolute path escapes repo_root."""
    target = (repo_root / diff.path).resolve()
    root = repo_root.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return SafetyVerdict(
            ok=False,
            rule="apply.path_escape",
            severity="ERROR",
            message=f"diff path {diff.path} resolves outside repo root",
        )
    return SafetyVerdict(ok=True)
