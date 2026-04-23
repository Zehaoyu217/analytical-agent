from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore


def test_ingest_two_notes_and_search_recovers_them(sb_home: Path, tmp_path: Path) -> None:
    a = tmp_path / "attention.md"
    a.write_text("# Attention\n\nSelf-attention is sufficient for seq transduction.\n")
    b = tmp_path / "recurrence.md"
    b.write_text("# Recurrence\n\nLong-range dependencies need recurrence.\n")

    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", str(a)]).exit_code == 0
    assert runner.invoke(cli, ["ingest", str(b)]).exit_code == 0
    assert runner.invoke(cli, ["reindex"]).exit_code == 0

    cfg = Config.load()
    with FtsStore.open(cfg.fts_path) as store:
        hits = store.search_sources("attention", k=5)
    assert any(h[0].startswith("src_attention") for h in hits)

    with DuckStore.open(cfg.duckdb_path) as store:
        rows = store.conn.execute("SELECT id FROM sources ORDER BY id").fetchall()
    assert len(rows) == 2
