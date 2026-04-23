from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.index.retriever import BM25Retriever, RetrievalHit
from second_brain.store.fts_store import FtsStore


def _seed(cfg: Config) -> None:
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    with FtsStore.open(cfg.fts_path) as store:
        store.ensure_schema()
        store.insert_source(
            source_id="src_attn", title="Attention is all you need",
            abstract="Self-attention architecture.", processed_body="transformer seq2seq",
            taxonomy="papers/ml",
        )
        store.insert_source(
            source_id="src_rnn", title="Sequence to Sequence",
            abstract="RNN encoder-decoder.", processed_body="recurrence",
            taxonomy="papers/ml",
        )


def test_search_sources_returns_hits(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    hits = BM25Retriever(cfg).search("attention", k=5, scope="sources")
    assert hits and isinstance(hits[0], RetrievalHit)
    assert hits[0].id == "src_attn"
    assert hits[0].kind == "source"
    assert hits[0].matched_field == "title"


def test_search_respects_k(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    hits = BM25Retriever(cfg).search("sequence", k=1, scope="sources")
    assert len(hits) == 1


def test_search_scope_both_merges_claims_and_sources(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    with FtsStore.open(cfg.fts_path) as store:
        store.insert_claim(
            claim_id="clm_attn", statement="Attention replaces recurrence.",
            abstract="", body="", taxonomy="papers/ml",
        )
    hits = BM25Retriever(cfg).search("attention", k=5, scope="both")
    kinds = {h.kind for h in hits}
    assert "source" in kinds and "claim" in kinds


def test_search_sources_can_return_chunks_with_provenance(sb_home: Path) -> None:
    cfg = Config.load()
    _seed(cfg)
    with FtsStore.open(cfg.fts_path) as store:
        store.insert_chunk(
            chunk_id="chk_attn_001",
            source_id="src_attn",
            source_title="Attention is all you need",
            section_title="Architecture",
            body="Self-attention computes weighted sums across tokens.",
            taxonomy="papers/ml",
            page_span="p.4",
        )
    hits = BM25Retriever(cfg).search("weighted sums", k=5, scope="sources")
    chunk = next(hit for hit in hits if hit.kind == "chunk")
    assert chunk.source_id == "src_attn"
    assert chunk.section_title == "Architecture"
    assert chunk.page_start == 4
