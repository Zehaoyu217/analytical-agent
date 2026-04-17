"""Tests for the dry-run sandbox."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.integrity.plugins.hooks_check.coverage import (
    CoverageRule,
    CoverageWhen,
    RequiredHook,
)
from backend.app.integrity.plugins.hooks_check.dry_run import (
    DryRunResult,
    run_for,
)
from backend.app.integrity.plugins.hooks_check.settings_parser import HookRecord


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _rule(paths: tuple[str, ...] = ("*.py",)) -> CoverageRule:
    return CoverageRule(
        id="r",
        description="d",
        when=CoverageWhen(paths=paths),
        requires_hook=RequiredHook(
            event="PostToolUse", matcher="Write", command_substring="echo",
        ),
    )


def _hook(command: str, matcher: str = "Write") -> HookRecord:
    return HookRecord(
        event="PostToolUse", matcher=matcher,
        command=command, source_index=(0, 0, 0),
    )


def test_green_hook_returns_exit_zero(tmp_path: Path) -> None:
    result = run_for(_rule(), _hook("echo green"), repo_root=tmp_path,
                     timeout=10, fixtures_dir=FIXTURES)
    assert isinstance(result, DryRunResult)
    assert result.exit_code == 0
    assert not result.timed_out
    assert "green" in result.stdout


def test_failing_hook_captures_nonzero(tmp_path: Path) -> None:
    result = run_for(_rule(), _hook("echo bad >&2; false"),
                     repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert result.exit_code == 1
    assert "bad" in result.stderr


def test_timeout_marks_timed_out(tmp_path: Path) -> None:
    result = run_for(_rule(), _hook("sleep 5"),
                     repo_root=tmp_path, timeout=1, fixtures_dir=FIXTURES)
    assert result.timed_out
    assert result.exit_code is None


def test_stdout_truncated_at_4kb(tmp_path: Path) -> None:
    # Print 8KB of 'a' — should be truncated to 4 KB.
    cmd = "python3 -c \"print('a'*8192, end='')\""
    result = run_for(_rule(), _hook(cmd),
                     repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert len(result.stdout) <= 4096


def test_fixture_extension_picks_correct_sample(tmp_path: Path) -> None:
    # rule with *.tsx in paths → should use sample.tsx fixture
    rule = _rule(paths=("frontend/src/**/*.tsx",))
    # Hook just echoes the file path it received via stdin → we read it back.
    cmd = (
        'python3 -c "import sys, json; '
        'data = json.load(sys.stdin); '
        'print(data[\\"tool_input\\"][\\"file_path\\"])"'
    )
    result = run_for(rule, _hook(cmd),
                     repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert ".tsx" in result.stdout
    assert result.exit_code == 0


def test_unknown_extension_falls_back_to_sample_md(tmp_path: Path) -> None:
    rule = _rule(paths=("docs/**",))  # no extension → fallback
    cmd = (
        'python3 -c "import sys, json; '
        'data = json.load(sys.stdin); '
        'print(data[\\"tool_input\\"][\\"file_path\\"])"'
    )
    result = run_for(rule, _hook(cmd),
                     repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert result.exit_code == 0
    assert result.stdout.strip().endswith(".md")


def test_subprocess_exception_returns_broken_result(tmp_path: Path) -> None:
    # Using a clearly invalid shell command structure that our wrapper handles.
    # Most shells will exit non-zero here, but if shutil.which("/bin/sh") fails
    # (it shouldn't on macOS/Linux), the caller still gets a DryRunResult.
    result = run_for(_rule(), _hook("nonexistent-binary-xyz-123"),
                     repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert result.exit_code != 0


def test_skill_md_glob_picks_skill_md_fixture(tmp_path: Path) -> None:
    rule = _rule(paths=("backend/app/skills/**/SKILL.md",))
    cmd = (
        'python3 -c "import sys, json, pathlib; '
        'data = json.load(sys.stdin); '
        'p = pathlib.Path(data[\\"tool_input\\"][\\"file_path\\"]); '
        'print(p.name)"'
    )
    result = run_for(rule, _hook(cmd),
                     repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert "SKILL.md" in result.stdout
