"""Safety tests for dry_run.run_for — confirm sandboxing actually sandboxes."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from backend.app.integrity.plugins.hooks_check.coverage import (
    CoverageRule,
    CoverageWhen,
    RequiredHook,
)
from backend.app.integrity.plugins.hooks_check.dry_run import (
    _sanitized_env,
    run_for,
)
from backend.app.integrity.plugins.hooks_check.settings_parser import HookRecord


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _rule(paths=("*.py",)) -> CoverageRule:
    return CoverageRule(
        id="r", description="d",
        when=CoverageWhen(paths=paths),
        requires_hook=RequiredHook(
            event="PostToolUse", matcher="Write", command_substring="",
        ),
    )


def _hook(command: str) -> HookRecord:
    return HookRecord(event="PostToolUse", matcher="Write",
                      command=command, source_index=(0, 0, 0))


def test_repo_root_is_not_modified(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "important.py").write_text("KEEP_ME")
    cmd = f"echo NUKED > {repo}/important.py"
    run_for(_rule(), _hook(cmd), repo_root=repo, timeout=10, fixtures_dir=FIXTURES)
    relative_cmd = "echo NUKED > scratch.py"
    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    (repo2 / "scratch.py").write_text("ORIGINAL")
    run_for(_rule(), _hook(relative_cmd), repo_root=repo2, timeout=10,
            fixtures_dir=FIXTURES)
    assert (repo2 / "scratch.py").read_text() == "ORIGINAL"


def test_path_preserved_in_env(tmp_path: Path) -> None:
    env = _sanitized_env()
    assert "PATH" in env
    assert env["PATH"]


def test_secret_env_keys_stripped() -> None:
    env_before = {
        "PATH": "/usr/bin",
        "GITHUB_TOKEN": "ghp_xxx",
        "OPENAI_API_KEY": "sk-xxx",
        "MY_SECRET": "s",
        "DB_PASSWORD": "p",
        "AWS_CREDENTIAL": "c",
        "SAFE_VAR": "v",
        "HOME": "/h",
    }
    with patch.dict(os.environ, env_before, clear=True):
        env = _sanitized_env()
    assert "GITHUB_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert "MY_SECRET" not in env
    assert "DB_PASSWORD" not in env
    assert "AWS_CREDENTIAL" not in env
    assert env.get("PATH") == "/usr/bin"
    assert env.get("HOME") == "/h"


def test_lc_locale_vars_passed_through() -> None:
    with patch.dict(os.environ, {"LC_ALL": "en_US.UTF-8", "PATH": "/usr/bin"}, clear=True):
        env = _sanitized_env()
    assert env.get("LC_ALL") == "en_US.UTF-8"


def test_tempdir_cleaned_up_after_run(tmp_path: Path) -> None:
    import glob as _glob
    before = set(_glob.glob("/tmp/hooks_dry_*")) | set(
        _glob.glob(f"{tempfile_root()}/hooks_dry_*"))
    run_for(_rule(), _hook("echo done"), repo_root=tmp_path, timeout=10,
            fixtures_dir=FIXTURES)
    after = set(_glob.glob("/tmp/hooks_dry_*")) | set(
        _glob.glob(f"{tempfile_root()}/hooks_dry_*"))
    assert not (after - before)


def tempfile_root() -> str:
    import tempfile
    return tempfile.gettempdir()


def test_fixture_files_unmodified_after_run(tmp_path: Path) -> None:
    py_fixture = FIXTURES / "sample.py"
    original = py_fixture.read_bytes()
    cmd = "echo CLOBBERED > sample.py"
    run_for(_rule(paths=("scripts/*.py",)), _hook(cmd),
            repo_root=tmp_path, timeout=10, fixtures_dir=FIXTURES)
    assert py_fixture.read_bytes() == original
