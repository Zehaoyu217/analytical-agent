"""Tests for VectorRetriever over sqlite-vec."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("sqlite_vec")

from second_brain.config import Config  # noqa: E402
from second_brain.index.vector_retriever import VectorRetriever  # noqa: E402
from second_brain.index.vector_store import VectorStore  # noqa: E402


class FakeEmbedder:
    def __init__(self, mapping: dict[str, list[float]], dim: int):
        self.mapping = mapping
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping[t] for t in texts]


def _unit(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]


@pytest.fixture()
def seeded_cfg(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    vectors = {
        "clm_a": _unit([1.0, 0.0, 0.0]),
        "clm_b": _unit([0.0, 1.0, 0.0]),
        "clm_c": _unit([0.0, 0.0, 1.0]),
        "src_a": _unit([1.0, 0.0, 0.0]),
    }
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        for id_, v in vectors.items():
            kind = "claim" if id_.startswith("clm_") else "source"
            store.upsert(kind, id_, v)
    return cfg, vectors


def test_vector_retriever_returns_closest(seeded_cfg):
    cfg, vectors = seeded_cfg
    query_vec = _unit([0.95, 0.05, 0.0])
    embedder = FakeEmbedder({"q": query_vec}, dim=3)
    retriever = VectorRetriever(cfg, embedder=embedder)
    hits = retriever.search("q", k=3, scope="claims")
    assert hits[0].id == "clm_a"
    assert all(h.kind == "claim" for h in hits)
    assert all(h.matched_field == "vector" for h in hits)


def test_vector_retriever_scope_sources(seeded_cfg):
    cfg, _ = seeded_cfg
    embedder = FakeEmbedder({"q": _unit([1.0, 0.0, 0.0])}, dim=3)
    retriever = VectorRetriever(cfg, embedder=embedder)
    hits = retriever.search("q", k=3, scope="sources")
    assert all(h.kind == "source" for h in hits)
    assert hits[0].id == "src_a"


def test_vector_retriever_scope_both(seeded_cfg):
    cfg, _ = seeded_cfg
    embedder = FakeEmbedder({"q": _unit([1.0, 0.0, 0.0])}, dim=3)
    retriever = VectorRetriever(cfg, embedder=embedder)
    hits = retriever.search("q", k=5, scope="both")
    kinds = {h.kind for h in hits}
    assert kinds == {"claim", "source"}


def test_vector_retriever_scores_are_descending(seeded_cfg):
    cfg, _ = seeded_cfg
    embedder = FakeEmbedder({"q": _unit([1.0, 0.0, 0.0])}, dim=3)
    retriever = VectorRetriever(cfg, embedder=embedder)
    hits = retriever.search("q", k=3, scope="claims")
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 < s <= 1.0 for s in scores)


def test_vector_retriever_empty_query_returns_empty(seeded_cfg):
    cfg, _ = seeded_cfg
    embedder = FakeEmbedder({}, dim=3)
    retriever = VectorRetriever(cfg, embedder=embedder)
    assert retriever.search("", k=3) == []


def test_vector_retriever_missing_store_returns_empty(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    embedder = FakeEmbedder({"q": [1.0, 0.0, 0.0]}, dim=3)
    retriever = VectorRetriever(cfg, embedder=embedder)
    assert retriever.search("q", k=3) == []
