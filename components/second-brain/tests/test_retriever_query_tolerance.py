"""Retriever should handle natural-language prompts, not just FTS5 syntax."""
from __future__ import annotations

from second_brain.config import Config
from second_brain.index.retriever import BM25Retriever, _to_fts_query
from second_brain.store.fts_store import FtsStore


def test_to_fts_query_drops_stopwords_and_ors_terms():
    assert _to_fts_query("tell me about the knowledge graph") == '"knowledge" OR "graph"'


def test_to_fts_query_preserves_explicit_boolean_expressions():
    assert _to_fts_query('"knowledge graph"') == '"knowledge graph"'
    assert _to_fts_query("knowledge AND graph") == "knowledge AND graph"


def test_to_fts_query_empty_when_all_stopwords():
    # Falls back to the original string so FTS5 can raise / return nothing
    # rather than us silently dropping the whole query.
    assert _to_fts_query("is it the") == "is it the"


def test_retriever_finds_claim_for_natural_prompt(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    (home / ".sb").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()

    with FtsStore.open(cfg.fts_path) as store:
        store.ensure_schema()
        store.insert_claim(
            claim_id="clm_x",
            statement="Second-brain is a personal knowledge graph.",
            abstract="",
            body="",
            taxonomy="notes/test",
        )

    hits = BM25Retriever(cfg).search("tell me about the knowledge graph", k=3, scope="claims")
    assert len(hits) == 1
    assert hits[0].id == "clm_x"
