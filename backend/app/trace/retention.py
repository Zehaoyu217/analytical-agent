"""Retention CLI: delete traces by --clear-all / --older-than / --grade.

Usage:
    python -m app.trace.retention --clear-all
    python -m app.trace.retention --older-than 30d
    python -m app.trace.retention --grade A,B        # keep A and B, delete rest
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import yaml


def delete_all(traces_dir: Path) -> int:
    if not traces_dir.exists():
        return 0
    count = 0
    for path in traces_dir.glob("*.yaml"):
        path.unlink()
        count += 1
    return count


def delete_by_age(traces_dir: Path, older_than_days: int) -> int:
    if not traces_dir.exists():
        return 0
    cutoff = time.time() - older_than_days * 86400
    count = 0
    for path in traces_dir.glob("*.yaml"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            count += 1
    return count


def delete_by_grade(traces_dir: Path, keep_grades: set[str]) -> int:
    if not traces_dir.exists():
        return 0
    count = 0
    for path in traces_dir.glob("*.yaml"):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(raw, dict):
            continue
        summary = raw.get("summary")
        if not isinstance(summary, dict):
            continue
        grade = summary.get("final_grade")
        if grade not in keep_grades:
            path.unlink()
            count += 1
    return count


_AGE_RE = re.compile(r"^(\d+)d$")


def _parse_age(spec: str) -> int:
    match = _AGE_RE.match(spec)
    if not match:
        raise argparse.ArgumentTypeError(f"invalid age spec: {spec}; use e.g. '30d'")
    return int(match.group(1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.trace.retention")
    parser.add_argument("--clear-all", action="store_true")
    parser.add_argument("--older-than", type=_parse_age, metavar="Nd")
    parser.add_argument("--grade", type=str, help="comma-separated grades to keep")
    parser.add_argument(
        "--traces-dir",
        default=os.environ.get("TRACE_DIR", "traces"),
    )
    args = parser.parse_args(argv)

    traces_dir = Path(args.traces_dir)
    flag_count = sum(1 for f in (args.clear_all, args.older_than, args.grade) if f)
    if flag_count != 1:
        parser.error("exactly one of --clear-all / --older-than / --grade required")

    if args.clear_all:
        deleted = delete_all(traces_dir)
    elif args.older_than is not None:
        deleted = delete_by_age(traces_dir, args.older_than)
    else:
        keep = {g.strip() for g in args.grade.split(",") if g.strip()}
        deleted = delete_by_grade(traces_dir, keep)
    print(f"deleted {deleted} trace(s) from {traces_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
