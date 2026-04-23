from __future__ import annotations

from pathlib import Path

from second_brain.store.fts_store import FtsStore


def test_creates_virtual_tables(tmp_path: Path) -> None:
    db = tmp_path / "kb.sqlite"
    with FtsStore.open(db) as store:
        store.ensure_schema()
        names = store.list_tables()
    assert "source_fts" in names
    assert "claim_fts" in names
    assert "chunk_fts" in names
    assert "center_fts" in names


def test_insert_and_bm25_search(tmp_path: Path) -> None:
    db = tmp_path / "kb.sqlite"
    with FtsStore.open(db) as store:
        store.ensure_schema()
        store.insert_source(
            source_id="src_a",
            title="Attention Is All You Need",
            abstract="Transformer architecture using self-attention.",
            processed_body="The model relies entirely on self-attention mechanisms.",
            taxonomy="papers/ml",
        )
        store.insert_source(
            source_id="src_b",
            title="Cooking with Cast Iron",
            abstract="A guide to seasoning cookware.",
            processed_body="Cast iron pans benefit from polymerized oil.",
            taxonomy="notes/personal",
        )
        hits = store.search_sources("self attention", k=5)
    assert hits[0][0] == "src_a"
    assert hits[0][1] > 0


def test_atomic_swap(tmp_path: Path) -> None:
    target = tmp_path / "kb.sqlite"
    staging = tmp_path / "next" / "kb.sqlite"
    staging.parent.mkdir()
    with FtsStore.open(staging) as store:
        store.ensure_schema()
        store.insert_source(source_id="src_x", title="X", abstract="", processed_body="", taxonomy="")
    FtsStore.atomic_swap(staging=staging, target=target)
    assert target.exists()
    with FtsStore.open(target) as store:
        hits = store.search_sources("X", k=5)
    assert hits and hits[0][0] == "src_x"


def test_insert_and_search_chunks(tmp_path: Path) -> None:
    db = tmp_path / "kb.sqlite"
    with FtsStore.open(db) as store:
        store.ensure_schema()
        store.insert_chunk(
            chunk_id="chk_demo_001",
            source_id="src_demo",
            source_title="Attention",
            section_title="Architecture",
            body="Self-attention computes weighted sums across tokens.",
            taxonomy="papers/ml",
            page_span="p.3",
        )
        hits = store.search_chunks("weighted sums", k=5)
    assert hits
    assert hits[0][0] == "chk_demo_001"
    assert hits[0][1] == "src_demo"
    assert hits[0][4] == "p.3"
