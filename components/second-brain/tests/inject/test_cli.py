import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _init_kb_with_claim(home: Path) -> None:
    (home / ".sb").mkdir(parents=True, exist_ok=True)
    # Build a minimal FTS5 index directly so we don't need a full ingest+extract cycle.
    db = sqlite3.connect(home / ".sb" / "kb.sqlite")
    db.executescript(
        """
        CREATE VIRTUAL TABLE claim_fts USING fts5(
            claim_id UNINDEXED, statement, abstract, body, taxonomy,
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE VIRTUAL TABLE source_fts USING fts5(
            source_id UNINDEXED, title, abstract, processed_body, taxonomy,
            tokenize='unicode61 remove_diacritics 2'
        );
        INSERT INTO claim_fts(claim_id, statement, abstract, body, taxonomy)
        VALUES ('clm_attention-replaces-recurrence',
                'Self-attention alone is sufficient for seq transduction',
                'Self-attention is sufficient', 'body', 'papers/ml');
        """
    )
    db.commit()
    db.close()


def test_sb_inject_prints_block_for_matching_prompt(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(cli, ["inject", "--prompt", "attention transduction"])
    assert res.exit_code == 0, res.output
    assert "Second Brain" in res.output
    assert "clm_attention-replaces-recurrence" in res.output


def test_sb_inject_silent_on_skip_pattern(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(cli, ["inject", "--prompt", "/help"])
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_sb_inject_json_flag_returns_metadata(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(
        cli, ["inject", "--prompt", "attention transduction", "--json"]
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["hit_ids"] == ["clm_attention-replaces-recurrence"]
    assert payload["skipped_reason"] is None
    assert "clm_attention-replaces-recurrence" in payload["block"]


def test_sb_inject_disabled_via_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    (home / ".sb" / "habits.yaml").write_text(
        "injection:\n  enabled: false\n", encoding="utf-8"
    )
    res = CliRunner().invoke(cli, ["inject", "--prompt", "anything"])
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_sb_inject_stdin(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(
        cli, ["inject", "--prompt-stdin"], input="attention transduction\n"
    )
    assert res.exit_code == 0
    assert "clm_attention-replaces-recurrence" in res.output
