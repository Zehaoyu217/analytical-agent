from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _ingest_two(runner: CliRunner, tmp_path: Path) -> None:
    a = tmp_path / "attn.md"
    a.write_text("# Attention\n\nSelf-attention is sufficient for seq transduction.\n")
    b = tmp_path / "rnn.md"
    b.write_text("# Recurrence\n\nRNNs carry hidden state.\n")
    assert runner.invoke(cli, ["ingest", str(a)]).exit_code == 0
    assert runner.invoke(cli, ["ingest", str(b)]).exit_code == 0
    assert runner.invoke(cli, ["reindex"]).exit_code == 0


def test_cli_search_json_output(sb_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    _ingest_two(runner, tmp_path)
    result = runner.invoke(cli, ["search", "--json", "attention"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any(h["id"].startswith("src_attention") for h in payload)


def test_cli_load_returns_node(sb_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    _ingest_two(runner, tmp_path)
    # find actual slug
    search = runner.invoke(cli, ["search", "--json", "attention"])
    first_id = json.loads(search.output)[0]["id"]
    result = runner.invoke(cli, ["load", "--json", first_id])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["root"]["id"] == first_id
