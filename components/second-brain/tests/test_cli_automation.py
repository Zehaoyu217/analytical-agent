from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_cli_process_inbox_reports_ok_and_failures(sb_home: Path):
    (sb_home / "inbox" / "idea.md").write_text("# Idea\n\nnote.\n")
    (sb_home / "inbox" / "bad.xyz").write_bytes(b"junk")

    runner = CliRunner()
    result = runner.invoke(cli, ["process-inbox"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "FAILED" in result.output
    assert "bad.xyz" in result.output


def test_cli_process_inbox_exits_0_on_empty_inbox(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["process-inbox"])
    assert result.exit_code == 0
    assert "empty" in result.output.lower()


from second_brain.frontmatter import dump_document


def test_cli_ingest_retry_rehydrates_failed_source(sb_home: Path):
    folder = sb_home / "sources" / "src_note_sample_1"
    (folder / "raw").mkdir(parents=True)
    (folder / "raw" / "note.md").write_text("# Good\n\nbody.\n")
    dump_document(
        folder / "_source.md",
        {
            "id": "src_note_sample_1",
            "title": "note-sample-1",
            "kind": "failed",
            "content_hash": "sha256-x",
            "ingested_at": "2026-04-18T00:00:00Z",
            "raw": [{"path": "raw/note.md", "kind": "note", "sha256": "x"}],
        },
        "placeholder",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--retry", "src_note_sample_1"])
    assert result.exit_code == 0, result.output
    assert "retry ok" in result.output.lower()


def test_cli_watch_once_drains_then_exits(sb_home: Path, monkeypatch: pytest.MonkeyPatch):
    """--once mode enqueues current inbox contents, drains, and exits — for cron-style usage."""
    (sb_home / "inbox" / "note.md").write_text("# x\n\nbody.\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["watch", "--once"])
    assert result.exit_code == 0, result.output
    assert "drained" in result.output.lower() or "processed" in result.output.lower()
    assert any((sb_home / "sources").iterdir())


def test_cli_maintain_prints_report(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["maintain"])
    assert result.exit_code == 0, result.output
    assert "lint" in result.output.lower()
    assert "contradictions" in result.output.lower()
    assert "compact" in result.output.lower()


def test_cli_maintain_json_flag_emits_json(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["maintain", "--json"])
    assert result.exit_code == 0, result.output
    import json as _json

    payload = _json.loads(result.output)
    assert "lint_counts" in payload
    assert "stale_abstracts" in payload
