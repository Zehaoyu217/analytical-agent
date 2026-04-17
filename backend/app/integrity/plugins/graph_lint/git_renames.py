from __future__ import annotations

import subprocess
from pathlib import Path


def parse_renames(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].startswith("R"):
            old, new = parts[1], parts[2]
            out[old] = new
    return out


def recent_renames(
    repo_root: Path, *, since: str = "1.day.ago", git_bin: str = "git"
) -> dict[str, str]:
    cmd = [git_bin, "log", f"--since={since}", "--diff-filter=R", "--name-status", "--format="]
    try:
        proc = subprocess.run(
            cmd, cwd=str(repo_root), capture_output=True, text=True, check=False, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}
    return parse_renames(proc.stdout)
