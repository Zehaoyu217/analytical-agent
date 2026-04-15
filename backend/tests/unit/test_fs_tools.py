"""Tests for FsTools — read-only filesystem access for the agent (P25)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.harness.fs_tools import FsTools


@pytest.fixture
def root(tmp_path: Path) -> Path:
    # Set up a small file tree
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "report.md").write_text("# Report\n\nContent here.")
    (tmp_path / "data" / "notes.txt").write_text("line1\nline2\nfoo bar\n")
    (tmp_path / ".env").write_text("SECRET=abc")
    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "nested.py").write_text("def hello(): pass\n")
    return tmp_path


@pytest.fixture
def fs(root: Path) -> FsTools:
    return FsTools(project_root=root)


# ── read_file ─────────────────────────────────────────────────────────────────


def test_read_file_returns_content(fs, root):
    result = fs.read_file({"path": "data/report.md"})
    assert result["ok"] is True
    assert "Content here" in result["content"]
    assert result["lines"] == 3


def test_read_file_path_escape(fs):
    result = fs.read_file({"path": "../../../etc/passwd"})
    assert result["ok"] is False
    assert result["error"] == "path_escape"


def test_read_file_banned_env(fs):
    result = fs.read_file({"path": ".env"})
    assert result["ok"] is False
    assert result["error"] == "path_forbidden"


def test_read_file_missing_file(fs):
    result = fs.read_file({"path": "data/nonexistent.md"})
    assert result["ok"] is False
    assert "not_found" in result["error"]


# ── glob_files ────────────────────────────────────────────────────────────────


def test_glob_files_matches_pattern(fs):
    result = fs.glob_files({"pattern": "**/*.md"})
    assert result["ok"] is True
    paths = result["files"]
    assert any("report.md" in p for p in paths)
    assert not any(".env" in p for p in paths)


def test_glob_files_caps_at_200(fs, root):
    for i in range(210):
        (root / f"file_{i}.txt").write_text(f"content {i}")
    result = fs.glob_files({"pattern": "*.txt"})
    assert result["ok"] is True
    assert result["count"] <= 200
    assert len(result["files"]) <= 200


def test_glob_files_path_escape(fs):
    result = fs.glob_files({"pattern": "../**/*.py"})
    assert result["ok"] is False
    assert result["error"] == "path_escape"


# ── search_text ───────────────────────────────────────────────────────────────


def test_search_text_finds_matches(fs):
    result = fs.search_text({"pattern": "foo", "path": "data"})
    assert result["ok"] is True
    matches = result["matches"]
    assert len(matches) >= 1
    assert any("foo" in m["text"] for m in matches)
    assert all("file" in m for m in matches)
    assert all("line" in m for m in matches)


def test_search_text_caps_at_50(fs, root):
    # Write a file with 60 matching lines
    lines = "\n".join(f"needle {i}" for i in range(60))
    (root / "data" / "big.txt").write_text(lines)
    result = fs.search_text({"pattern": "needle", "path": "data"})
    assert result["ok"] is True
    assert len(result["matches"]) <= 50


def test_search_text_path_escape(fs):
    result = fs.search_text({"pattern": "foo", "path": "../.."})
    assert result["ok"] is False
    assert result["error"] == "path_escape"
