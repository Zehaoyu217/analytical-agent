from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def test_help(sb_home: Path) -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output
    assert "reindex" in result.output
    assert "status" in result.output


def test_status_empty_home(sb_home: Path) -> None:
    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "sources: 0" in result.output


def test_ingest_and_reindex_roundtrip(sb_home: Path, tmp_path: Path) -> None:
    note = tmp_path / "hello.md"
    note.write_text("# Hello\n\nBody.")
    result = CliRunner().invoke(cli, ["ingest", str(note)])
    assert result.exit_code == 0, result.output
    assert "src_" in result.output

    result = CliRunner().invoke(cli, ["reindex"])
    assert result.exit_code == 0

    result = CliRunner().invoke(cli, ["status"])
    assert "sources: 1" in result.output
