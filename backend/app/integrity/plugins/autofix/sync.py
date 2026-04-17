"""Plugin F sync: update config/autofix_state.yaml from merged autofix PRs.

Runs `gh pr list` over the lookback window, fetches each merged PR's first-commit
diff vs the merge commit's diff. Identical → "clean". Different → "human_edited".

Counters drive the circuit breaker: when human_edited > max_human_edits in
window_days, the class is auto-disabled by AutofixPlugin's load step.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from .circuit_breaker import (
    AutofixState,
    load_state,
    record_pr_outcome,
    save_state,
)

BRANCH_RE = re.compile(r"^integrity/autofix/(?P<class>[^/]+)/(?P<date>\d{4}-\d{2}-\d{2})$")


def _list_merged_prs(window_days: int, gh: str = "gh") -> list[dict]:
    proc = subprocess.run(
        [gh, "pr", "list",
         "--state", "merged",
         "--search", "head:integrity/autofix",
         "--limit", "200",
         "--json", "number,headRefName,mergedAt,state"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if proc.returncode != 0:
        return []
    return json.loads(proc.stdout or "[]")


def _diff_at_first_commit(repo_root: Path, branch: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", branch, "-n", "1",
         "--format=", "-p"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    return proc.stdout or ""


def _diff_at_merge(repo_root: Path, branch: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", f"main...{branch}"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    return proc.stdout or ""


def sync_state(
    *,
    repo_root: Path,
    state_path: Path,
    today: date | None = None,
    gh: str = "gh",
) -> AutofixState:
    today = today or date.today()
    state = load_state(state_path)
    cutoff = today - timedelta(days=state.window_days)
    prs = _list_merged_prs(state.window_days, gh=gh)

    for pr in prs:
        branch = str(pr.get("headRefName", ""))
        m = BRANCH_RE.match(branch)
        if not m:
            continue
        merged_at_iso = str(pr.get("mergedAt", ""))[:10]
        if not merged_at_iso:
            continue
        merged_date = datetime.strptime(merged_at_iso, "%Y-%m-%d").date()
        if merged_date < cutoff:
            continue

        original_diff = _diff_at_first_commit(repo_root, branch)
        merge_diff = _diff_at_merge(repo_root, branch)
        action = "clean" if original_diff == merge_diff else "human_edited"

        state = record_pr_outcome(
            state,
            fix_class=m.group("class"),
            pr=int(pr.get("number", 0)),
            merged_at=merged_at_iso,
            action=action,
            today=today,
        )

    save_state(state_path, state)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.integrity.plugins.autofix.sync"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--state-path", type=Path,
        default=None, help="Override state file path (default config/autofix_state.yaml)",
    )
    args = parser.parse_args(argv)
    state_path = args.state_path or (args.repo_root / "config" / "autofix_state.yaml")
    sync_state(repo_root=args.repo_root.resolve(), state_path=state_path)
    print(f"Synced {state_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
