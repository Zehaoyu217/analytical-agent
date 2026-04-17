"""Sandboxed dry-run for hook commands.

For each (rule, hook) pair, ``run_for`` synthesizes the kind of stdin payload
Claude Code emits at hook invocation time, copies a canonical fixture file
into a fresh tempdir, and runs the hook command via ``/bin/sh -c`` with
``cwd=tempdir`` and a sanitized environment.

Goals:
- Hook can mutate the temp file freely; never touches the real repo.
- Per-hook wall-clock cap (``timeout``); ``subprocess.TimeoutExpired`` →
  ``timed_out=True``, ``exit_code=None``.
- Secrets are stripped from the env before invocation.
- ``stdout`` / ``stderr`` truncated at 4 KB to keep artifact size sane.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .coverage import CoverageRule
from .settings_parser import HookRecord

OUTPUT_LIMIT = 4096
SECRET_RE = re.compile(r"_(TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL)$", re.IGNORECASE)
SAFE_ENV_KEYS = {
    "PATH", "HOME", "LANG", "TMPDIR", "SHELL", "USER", "LOGNAME",
    "TERM", "COLORTERM",
}
EXTENSION_FIXTURE = {
    ".py": "sample.py",
    ".tsx": "sample.tsx",
    ".ts": "sample.ts",
    ".md": "sample.md",
    ".sh": "sample.sh",
    ".yaml": "skill.yaml",
    ".yml": "skill.yaml",
}


@dataclass(frozen=True)
class DryRunResult:
    rule_id: str
    hook_command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


def run_for(
    rule: CoverageRule,
    hook: HookRecord,
    repo_root: Path,
    timeout: int,
    fixtures_dir: Path,
) -> DryRunResult:
    """Dry-run ``hook.command`` against a synthetic payload for ``rule``."""
    glob = rule.when.paths[0]
    fixture_name = _fixture_for(glob)
    fixture_path = fixtures_dir / fixture_name
    if not fixture_path.exists():
        # Internal invariant — fixtures shipped with the package.
        fixture_path = fixtures_dir / "sample.md"

    fixture_text = fixture_path.read_text(encoding="utf-8")
    rel_target = _materialize_path(glob, fixture_name)

    tool_name = _tool_for(hook.matcher)
    started = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    stdout = ""
    stderr = ""

    with tempfile.TemporaryDirectory(prefix="hooks_dry_") as td:
        tmp_root = Path(td)
        target = tmp_root / rel_target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fixture_text, encoding="utf-8")

        stdin_payload = json.dumps({
            "tool_name": tool_name,
            "tool_input": {
                "file_path": str(target),
                "content": fixture_text,
            },
        })
        env = _sanitized_env()
        try:
            completed = subprocess.run(
                ["/bin/sh", "-c", hook.command],
                input=stdin_payload,
                cwd=str(tmp_root),
                env=env,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
            exit_code = completed.returncode
            stdout = completed.stdout[:OUTPUT_LIMIT]
            stderr = completed.stderr[:OUTPUT_LIMIT]
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or "")[:OUTPUT_LIMIT] if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "")[:OUTPUT_LIMIT] if isinstance(exc.stderr, str) else ""
        except OSError as exc:
            exit_code = 127
            stderr = f"OSError: {exc}"[:OUTPUT_LIMIT]

    duration_ms = int((time.monotonic() - started) * 1000)
    return DryRunResult(
        rule_id=rule.id,
        hook_command=hook.command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
    )


def _sanitized_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if SECRET_RE.search(key):
            continue
        if key.startswith("LC_") or key in SAFE_ENV_KEYS:
            env[key] = value
    if "PATH" not in env:
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    return env


def _fixture_for(glob: str) -> str:
    """Pick the sample fixture matching ``glob``'s extension."""
    if glob.endswith("SKILL.md"):
        return "SKILL.md"
    if glob.endswith("skill.yaml"):
        return "skill.yaml"
    suffix = ""
    last_seg = glob.rsplit("/", 1)[-1]
    if "." in last_seg:
        suffix = "." + last_seg.rsplit(".", 1)[-1]
    return EXTENSION_FIXTURE.get(suffix, "sample.md")


def _materialize_path(glob: str, fixture_name: str) -> str:
    """Build a temp-file relative path that mimics the rule's glob shape."""
    parts = []
    for seg in glob.split("/"):
        if seg in {"**", "*"} or "*" in seg:
            continue
        if "." in seg.rsplit("/", 1)[-1]:
            continue  # strip the glob's filename — we'll attach our own
        parts.append(seg)
    if not parts:
        parts.append("scratch")
    parts.append(fixture_name)
    return "/".join(parts)


def _tool_for(matcher: str) -> str:
    tokens = sorted(t for t in matcher.split("|") if t)
    return tokens[0] if tokens else "Write"


def _cleanup_tempdir(path: Path) -> None:
    """Best-effort tempdir cleanup. ``TemporaryDirectory`` handles it normally."""
    shutil.rmtree(path, ignore_errors=True)
