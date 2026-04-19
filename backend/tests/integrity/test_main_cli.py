import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "graphify").mkdir()
    (tmp_path / "graphify" / "graph.json").write_text(
        json.dumps({"nodes": [], "links": []})
    )
    return tmp_path


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "backend.app.integrity", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent.parent)},
    )


def test_cli_runs_and_writes_report(repo: Path):
    result = run_cli(repo, "--no-augment")
    assert result.returncode == 0, result.stderr
    today_dirs = list((repo / "integrity-out").glob("*"))
    assert any((d / "report.json").exists() for d in today_dirs if d.is_dir())


def test_cli_plugin_filter_runs_only_named(repo: Path):
    result = run_cli(repo, "--no-augment", "--plugin", "graph_lint")
    assert result.returncode == 0, result.stderr


def test_cli_unknown_plugin_exits_nonzero(repo: Path):
    result = run_cli(repo, "--plugin", "nonexistent")
    assert result.returncode != 0
    assert "nonexistent" in result.stderr


def test_main_runs_only_doc_audit(tmp_path, monkeypatch):
    # Arrange: empty repo with just a CLAUDE.md and graphify stub
    (tmp_path / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    g = tmp_path / "graphify"
    g.mkdir()
    (g / "graph.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")

    from backend.app.integrity.__main__ import main

    rc = main(["--plugin", "doc_audit", "--repo-root", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "integrity-out" / __import__("datetime").date.today().isoformat() / "doc_audit.json").exists()  # noqa: E501


def test_main_rejects_unknown_plugin(tmp_path):
    g = tmp_path / "graphify"
    g.mkdir()
    (g / "graph.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")

    import pytest
    from backend.app.integrity.__main__ import main

    with pytest.raises(SystemExit):
        main(["--plugin", "nonexistent", "--repo-root", str(tmp_path)])


def test_hooks_check_in_known_plugins() -> None:
    from backend.app.integrity.__main__ import KNOWN_PLUGINS
    assert "hooks_check" in KNOWN_PLUGINS


def test_unknown_plugin_rejected_for_hooks_check_typo(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    from backend.app.integrity.__main__ import main
    try:
        main(["--plugin", "hooks_chec"])
    except SystemExit as exc:
        assert "unknown plugin" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
