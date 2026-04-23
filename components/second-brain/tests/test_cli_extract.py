from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def test_cli_extract_uses_fake_when_flag_set(sb_home: Path, tmp_path: Path,
                                              monkeypatch) -> None:
    # Ingest a note first
    note = tmp_path / "note.md"
    note.write_text("# Topic\n\nTopic has a claim worth recording.\n")
    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", str(note)]).exit_code == 0

    # Force fake client via env var
    monkeypatch.setenv(
        "SB_FAKE_CLAIMS",
        '[{"statement":"Topic exists.","kind":"empirical","confidence":"high",'
        '"scope":"","supports":[],"contradicts":[],"refines":[],"abstract":"t"}]',
    )
    result = runner.invoke(cli, ["extract", "src_topic"])
    assert result.exit_code == 0, result.output
    assert "1 claim" in result.output.lower() or "1 claims" in result.output.lower()
