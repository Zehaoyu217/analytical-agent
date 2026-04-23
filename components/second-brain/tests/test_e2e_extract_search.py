from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def test_e2e_flow(sb_home: Path, tmp_path: Path, monkeypatch) -> None:
    note = tmp_path / "attention.md"
    note.write_text("# Attention\n\nSelf-attention alone is sufficient.\n")

    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", str(note)]).exit_code == 0

    monkeypatch.setenv(
        "SB_FAKE_CLAIMS",
        json.dumps([{
            "statement": "Self-attention replaces recurrence.",
            "kind": "empirical", "confidence": "high",
            "scope": "seq2seq", "supports": [], "contradicts": [], "refines": [],
            "abstract": "attn vs rnn",
        }]),
    )
    assert runner.invoke(cli, ["extract", "src_attention"]).exit_code == 0
    assert runner.invoke(cli, ["reindex"]).exit_code == 0

    result = runner.invoke(cli, ["search", "--json", "--scope", "claims", "recurrence"])
    assert result.exit_code == 0
    hits = json.loads(result.output)
    assert hits and hits[0]["kind"] == "claim"
