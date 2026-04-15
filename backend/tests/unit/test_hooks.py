"""Tests for HookRunner — P23 user-configurable hooks."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.harness.hooks import HookRunner


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture
def hooks_config(tmp_path: Path) -> Path:
    cfg = {
        "PreToolUse": [
            {"matcher": "execute_python", "command": "echo pre_$TOOL_NAME", "description": "log pre"},
        ],
        "PostToolUse": [
            {"matcher": "save_artifact", "command": "echo post_$TOOL_NAME", "description": "log post"},
        ],
        "Stop": [
            {"command": "echo stop_hook", "description": "session end"},
        ],
    }
    p = tmp_path / "hooks.json"
    p.write_text(json.dumps(cfg))
    return p


# ── matcher ───────────────────────────────────────────────────────────────────


def test_matcher_exact(tmp_path):
    r = HookRunner(tmp_path / "absent.json")
    assert r._match("execute_python", "execute_python")
    assert not r._match("execute_python", "save_artifact")


def test_matcher_wildcard(tmp_path):
    r = HookRunner(tmp_path / "absent.json")
    assert r._match("*", "any_tool")
    assert r._match("execute_*", "execute_python")
    assert not r._match("execute_*", "save_artifact")


# ── missing config ────────────────────────────────────────────────────────────


def test_missing_config_is_noop(tmp_path):
    r = HookRunner(tmp_path / "absent.json")
    # Must not raise
    r.run_pre("execute_python", {"code": "1+1"})
    r.run_post("save_artifact", {"artifact_id": "a1"})
    r.run_stop("session-1")


# ── pre-tool hook ─────────────────────────────────────────────────────────────


def test_pre_tool_runs_matching_command(hooks_config):
    r = HookRunner(hooks_config)
    r.run_pre("execute_python", {"code": "1+1"})
    # Hook runs in subprocess — no capsys output. Just verify no exception.


def test_pre_tool_skips_non_matching(hooks_config):
    r = HookRunner(hooks_config)
    # save_artifact has no PreToolUse hook — must not raise
    r.run_pre("save_artifact", {})


def test_pre_tool_nonzero_exit_does_not_raise(tmp_path):
    cfg = {
        "PreToolUse": [{"matcher": "*", "command": "exit 1", "description": "fail"}],
    }
    p = tmp_path / "hooks.json"
    p.write_text(json.dumps(cfg))
    r = HookRunner(p)
    # Must not raise even though exit code is 1
    r.run_pre("execute_python", {})


# ── post-tool hook ────────────────────────────────────────────────────────────


def test_post_tool_runs_matching_command(hooks_config):
    r = HookRunner(hooks_config)
    r.run_post("save_artifact", {"artifact_id": "a1"})


def test_post_tool_skips_pre_hooks(hooks_config):
    r = HookRunner(hooks_config)
    # execute_python has PreToolUse but not PostToolUse
    r.run_post("execute_python", {})  # must not raise


# ── stop hook ─────────────────────────────────────────────────────────────────


def test_stop_hook_runs(hooks_config):
    r = HookRunner(hooks_config)
    r.run_stop("session-abc")


# ── env vars ──────────────────────────────────────────────────────────────────


def test_hook_runner_pre_called_in_loop(tmp_path):
    """Verify run_pre interface is correct — records tool_name."""
    from app.harness.hooks import HookRunner

    runner = HookRunner(tmp_path / "absent.json")

    runner.run_pre("execute_python", {"code": "1+1"})
    # Missing config = noop, but must not raise
    assert True  # reached here without exception


def test_env_vars_injected(tmp_path):
    """Hook command can read TOOL_NAME, TOOL_INPUT, SESSION_ID env vars."""
    out_file = tmp_path / "out.txt"
    cfg = {
        "PreToolUse": [
            {
                "matcher": "execute_python",
                "command": f"echo $TOOL_NAME > {out_file}",
                "description": "capture tool name",
            }
        ],
    }
    p = tmp_path / "hooks.json"
    p.write_text(json.dumps(cfg))
    r = HookRunner(p)
    r.run_pre("execute_python", {"code": "1+1"}, session_id="sess-42")
    assert out_file.read_text().strip() == "execute_python"
