from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.repo import RepoConverter


@pytest.fixture
def seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "seed-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# seed-repo\n\nDemonstration repo.\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'seed'\n", encoding="utf-8")
    docs = repo / "docs"
    docs.mkdir()
    (docs / "arch.md").write_text("# Architecture\n\nSome docs.\n", encoding="utf-8")
    node_mods = repo / "node_modules"
    node_mods.mkdir()
    (node_mods / "ignore.md").write_text("# should be excluded\n", encoding="utf-8")

    for cmd in (
        ["git", "init", "--quiet"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def test_matches_repo_origin() -> None:
    c = RepoConverter()
    ok = IngestInput.from_bytes(origin="gh:owner/repo", suffix="", content=b"")
    ok2 = IngestInput.from_bytes(origin="https://github.com/owner/repo.git", suffix="", content=b"")
    bad = IngestInput.from_bytes(origin="https://example.com/a", suffix="", content=b"")
    assert c.matches(ok)
    assert c.matches(ok2)
    assert not c.matches(bad)


def test_convert_clones_and_captures_globs(tmp_path: Path, seed_repo: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_repo")
    inp = IngestInput.from_bytes(origin=f"file://{seed_repo}", suffix="", content=b"")
    c = RepoConverter(
        include_globs=("README*", "docs/**/*.md", "pyproject.toml"),
        exclude_globs=("node_modules/**", ".git/**"),
    )
    artifacts = c.convert(inp, folder)
    paths = {r.path for r in artifacts.raw}
    assert "raw/README.md" in paths
    assert "raw/pyproject.toml" in paths
    assert "raw/docs/arch.md" in paths
    assert not any("node_modules" in p for p in paths)
    assert "README.md" in artifacts.processed_body
    assert "seed-repo" in artifacts.title_hint


def test_resolve_gh_shorthand() -> None:
    c = RepoConverter()
    assert c._resolve("gh:acme/widgets") == "https://github.com/acme/widgets.git"
    assert c._resolve("https://github.com/acme/widgets.git") == "https://github.com/acme/widgets.git"
    assert c._resolve("file:///tmp/x") == "file:///tmp/x"


def test_rejects_unsafe_input() -> None:
    c = RepoConverter()
    with pytest.raises(ValueError):
        c._resolve("gh:acme/widgets; rm -rf /")
