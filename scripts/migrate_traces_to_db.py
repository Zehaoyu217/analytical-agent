#!/usr/bin/env python3
"""Migrate existing YAML trace files to sessions.db.

Usage:
    uv run python scripts/migrate_traces_to_db.py [--dry-run]

Scans the legacy traces directory (TRACE_DIR or $CCAGENT_HOME/traces),
parses each YAML file into Session + Message rows, and inserts them into
sessions.db. Already-present sessions are skipped (idempotent).

Summary printed at the end: N migrated, M skipped, K failed.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent / "backend"


def _add_backend_to_path() -> None:
    br = str(_backend_root())
    if br not in sys.path:
        sys.path.insert(0, br)


def _run(dry_run: bool) -> None:
    _add_backend_to_path()

    from app.core.home import sessions_db_path, traces_path  # noqa: PLC0415
    from app.storage.session_db import SessionDB  # noqa: PLC0415

    traces_dir = Path(
        __import__("os").environ.get("TRACE_DIR", str(traces_path()))
    )
    db = SessionDB(db_path=sessions_db_path())

    if not traces_dir.exists():
        print(f"Traces directory not found: {traces_dir}")
        print("Nothing to migrate.")
        return

    yaml_files = sorted(traces_dir.glob("*.yaml"))
    print(f"Found {len(yaml_files)} trace file(s) in {traces_dir}")

    migrated = 0
    skipped = 0
    failed = 0

    for path in yaml_files:
        session_id = path.stem
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("not a dict")

            # Check if already migrated
            if db.get_session(session_id) is not None:
                skipped += 1
                continue

            if dry_run:
                print(f"  [dry-run] would migrate {session_id}")
                migrated += 1
                continue

            summary = raw.get("summary", {})
            events = raw.get("events", [])

            # Infer goal from first user-facing event
            goal = summary.get("input_query", "")
            if not goal:
                for ev in events:
                    if ev.get("kind") == "session_start":
                        goal = ev.get("input_query", "")
                        break

            db.create_session(
                id=session_id,
                goal=goal[:300] if goal else None,
                source="chat",
            )

            for ev in events:
                kind = ev.get("kind", "")
                if kind == "llm_call":
                    db.append_message(
                        session_id=session_id,
                        role="assistant",
                        content=ev.get("response_text"),
                        step_index=ev.get("turn"),
                    )
                elif kind == "tool_call":
                    db.append_message(
                        session_id=session_id,
                        role="tool",
                        content=None,
                        tool_calls={
                            "name": ev.get("tool_name"),
                            "input": ev.get("tool_input", {}),
                        },
                        tool_result={"output": ev.get("tool_output")} if ev.get("tool_output") else None,
                        step_index=ev.get("turn"),
                    )
                elif kind == "final_output":
                    db.append_message(
                        session_id=session_id,
                        role="assistant",
                        content=ev.get("output_text"),
                    )

            db.finalize_session(
                id=session_id,
                outcome=summary.get("outcome"),
                step_count=summary.get("turn_count", 0),
                input_tokens=summary.get("total_input_tokens", 0),
                output_tokens=summary.get("total_output_tokens", 0),
            )
            migrated += 1
            print(f"  migrated {session_id}")

        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAILED {session_id}: {exc}", file=sys.stderr)

    verb = "would migrate" if dry_run else "migrated"
    print(f"\nDone: {migrated} {verb}, {skipped} skipped, {failed} failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be migrated without writing to the DB",
    )
    args = parser.parse_args()
    _run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
