"""PR dispatcher for Plugin F autofix.

Per fix class, runs the 8-step apply flow:
  1. Pre-check: empty diffs → skip; stale or path-escape → abort class
  2. Capture lease SHA
  3. Branch: fetch origin main + checkout -B autofix branch
  4. Apply: write new_content to disk + git add
  5. Commit: single commit with bulleted rationale
  6. Push: --force-with-lease
  7. Open or update PR
  8. Record result

All git/gh calls go through subprocess.run with explicit timeout. Per-class
isolation: one class failing does not affect siblings (caller's responsibility
to dispatch each class independently).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from .diff import Diff
from .safety import check_diff_path

ActionLiteral = Literal["created", "updated", "skipped", "dry_run", "errored"]


@dataclass(frozen=True)
class DispatcherConfig:
    repo_root: Path
    branch_prefix: str
    commit_author: str
    gh_executable: str
    subprocess_timeout_seconds: int
    today: date
    dry_run: bool


@dataclass(frozen=True)
class PRResult:
    fix_class: str
    action: ActionLiteral
    branch: str = ""
    pr_number: int | None = None
    pr_url: str = ""
    diff_count: int = 0
    error_rule: str = ""
    error_message: str = ""


def _branch_name(prefix: str, fix_class: str, today: date) -> str:
    return f"{prefix}/{fix_class}/{today.isoformat()}"


def _build_pr_body(fix_class: str, diffs: list[Diff]) -> str:
    lines = ["## Issues fixed", ""]
    for d in diffs:
        for ref in d.source_issues:
            lines.append(f"- **{ref.plugin}.{ref.rule}** — {ref.message}")
    lines.append("")
    lines.append("## Diffs")
    lines.append("")
    for d in diffs:
        lines.append(f"- `{d.path}` — {d.rationale}")
    lines.append("")
    lines.append("## How to verify")
    lines.append("")
    lines.append("```bash")
    lines.append("make integrity-autofix  # re-run dry-run; this branch should produce no diffs")
    lines.append("```")
    return "\n".join(lines)


def _run_git(cfg: DispatcherConfig, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cfg.repo_root), *args],
        capture_output=True, text=True,
        timeout=cfg.subprocess_timeout_seconds,
        check=check,
    )


def _run_gh(cfg: DispatcherConfig, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [cfg.gh_executable, *args],
        capture_output=True, text=True,
        timeout=cfg.subprocess_timeout_seconds,
        check=check,
    )


def dispatch_class(
    fix_class: str,
    diffs: list[Diff],
    cfg: DispatcherConfig,
) -> PRResult:
    branch = _branch_name(cfg.branch_prefix, fix_class, cfg.today)

    if not diffs:
        return PRResult(fix_class=fix_class, action="skipped", branch=branch)

    for d in diffs:
        verdict = check_diff_path(d, cfg.repo_root)
        if not verdict.ok:
            return PRResult(
                fix_class=fix_class, action="errored", branch=branch,
                diff_count=len(diffs),
                error_rule=verdict.rule, error_message=verdict.message,
            )
        if d.stale_against(cfg.repo_root):
            return PRResult(
                fix_class=fix_class, action="errored", branch=branch,
                diff_count=len(diffs),
                error_rule="apply.stale_diff",
                error_message=f"diff for {d.path} stale: disk changed since proposal",
            )

    if cfg.dry_run:
        return PRResult(
            fix_class=fix_class, action="dry_run", branch=branch,
            diff_count=len(diffs),
        )

    lease = _run_git(cfg, "ls-remote", "origin", f"refs/heads/{branch}", check=False)
    lease_sha = (lease.stdout.split("\t", 1)[0] if lease.stdout else "")

    _run_git(cfg, "fetch", "origin", "main")
    _run_git(cfg, "checkout", "-B", branch, "origin/main")

    for d in diffs:
        target = cfg.repo_root / d.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(d.new_content)
        _run_git(cfg, "add", str(d.path))

    title = f"chore(integrity): {fix_class}"
    body = "\n".join(f"- {d.rationale}" for d in diffs)
    _run_git(
        cfg, "-c", "user.name=Integrity Autofix",
        "-c", "user.email=integrity@local",
        "commit", "-m", title, "-m", body,
    )

    push_arg = f"--force-with-lease={branch}:{lease_sha}" if lease_sha else "--force-with-lease"
    _run_git(cfg, "push", push_arg, "origin", branch)

    listing = _run_gh(cfg, "pr", "list", "--head", branch, "--json", "number,url")
    pr_list = json.loads(listing.stdout or "[]")

    pr_body = _build_pr_body(fix_class, diffs)
    body_file = cfg.repo_root / ".autofix_body.md"
    body_file.write_text(pr_body)
    try:
        pr_num: int | None
        if pr_list:
            pr_num = int(pr_list[0]["number"])
            pr_url = str(pr_list[0].get("url", ""))
            _run_gh(cfg, "pr", "edit", str(pr_num), "--body-file", str(body_file))
            action: ActionLiteral = "updated"
        else:
            create = _run_gh(
                cfg, "pr", "create",
                "--title", title,
                "--body-file", str(body_file),
                "--base", "main",
                "--head", branch,
                "--json", "number,url",
            )
            payload = json.loads(create.stdout or "{}")
            pr_num = int(payload.get("number", 0)) or None
            pr_url = str(payload.get("url", ""))
            action = "created"
    finally:
        body_file.unlink(missing_ok=True)

    return PRResult(
        fix_class=fix_class, action=action, branch=branch,
        pr_number=pr_num, pr_url=pr_url, diff_count=len(diffs),
    )
