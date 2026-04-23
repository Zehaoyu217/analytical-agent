from __future__ import annotations

import duckdb

from second_brain.config import Config
from second_brain.digest.passes.edge_audit import EdgeAuditPass
from second_brain.store.duckdb_store import DDL


def test_pass_conforms_to_protocol() -> None:
    from second_brain.digest.passes import Pass

    p = EdgeAuditPass()
    assert isinstance(p, Pass)
    assert p.prefix == "e"


def test_empty_kb_returns_empty(digest_cfg) -> None:
    assert EdgeAuditPass().run(digest_cfg, client=None) == []


def test_missing_duckdb_falls_back_to_markdown(digest_cfg, write_claim) -> None:
    # Retracted target + two active claims citing it → 2 drop_edge entries.
    write_claim(digest_cfg, "clm_bad", status="retracted")

    src_a = write_claim(digest_cfg, "clm_a")
    src_a.write_text(
        src_a.read_text(encoding="utf-8").replace(
            "supports: []", "supports: ['clm_bad']"
        ),
        encoding="utf-8",
    )
    src_b = write_claim(digest_cfg, "clm_b")
    src_b.write_text(
        src_b.read_text(encoding="utf-8").replace(
            "contradicts: []", "contradicts: ['clm_bad']"
        ),
        encoding="utf-8",
    )

    assert not digest_cfg.duckdb_path.exists()
    entries = EdgeAuditPass().run(digest_cfg, client=None)
    assert len(entries) == 2
    relations = {e.action["relation"] for e in entries}
    assert relations == {"supports", "contradicts"}
    for e in entries:
        assert e.action["action"] == "drop_edge"
        assert e.action["dst_id"] == "clm_bad"
        assert e.action["src_id"] in {"clm_a", "clm_b"}


def test_duckdb_source_preferred_over_markdown(digest_cfg: Config, write_claim) -> None:
    # Markdown has no edges — DB has two edges into retracted clm_bad.
    write_claim(digest_cfg, "clm_bad", status="retracted")
    write_claim(digest_cfg, "clm_a")
    write_claim(digest_cfg, "clm_b")

    conn = duckdb.connect(str(digest_cfg.duckdb_path))
    conn.execute(DDL)
    conn.execute(
        "INSERT INTO edges VALUES ('clm_a', 'clm_bad', 'supports', 'high', null, 'clm_a.md')"
    )
    conn.execute(
        "INSERT INTO edges VALUES ('clm_b', 'clm_bad', 'refines', 'high', null, 'clm_b.md')"
    )
    conn.close()

    entries = EdgeAuditPass().run(digest_cfg, client=None)
    assert len(entries) == 2
    assert {(e.action["src_id"], e.action["relation"]) for e in entries} == {
        ("clm_a", "supports"),
        ("clm_b", "refines"),
    }
    assert entries[0].section == "Edge audit"


def test_no_retracted_target_yields_empty(digest_cfg, write_claim) -> None:
    write_claim(digest_cfg, "clm_a")
    path = write_claim(digest_cfg, "clm_b")
    path.write_text(
        path.read_text(encoding="utf-8").replace("supports: []", "supports: ['clm_a']"),
        encoding="utf-8",
    )
    assert EdgeAuditPass().run(digest_cfg, client=None) == []


def test_duplicate_edges_dedup(digest_cfg, write_claim) -> None:
    write_claim(digest_cfg, "clm_bad", status="retracted")
    path = write_claim(digest_cfg, "clm_a")
    # Two relations; only one per (src,dst,relation) tuple.
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace("supports: []", "supports: ['clm_bad', 'clm_bad']"),
        encoding="utf-8",
    )
    entries = EdgeAuditPass().run(digest_cfg, client=None)
    assert len(entries) == 1
