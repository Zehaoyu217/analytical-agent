"""Tests for HybridRetriever + make_retriever factory."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("sqlite_vec")

from second_brain.config import Config  # noqa: E402
from second_brain.habits.loader import save_habits  # noqa: E402
from second_brain.habits.schema import Habits, RetrievalHabits  # noqa: E402
from second_brain.index.retriever import (  # noqa: E402
    BM25Retriever,
    HybridRetriever,
    make_retriever,
)
from second_brain.index.vector_store import VectorStore  # noqa: E402


def _unit(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]


class CannedEmbedder:
    """Embedder that maps query strings to preconfigured vectors."""

    def __init__(self, mapping: dict[str, list[float]], dim: int = 3):
        self.mapping = mapping
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping[t] for t in texts]


def _seed_fts(path: Path, rows: list[tuple[str, str]]) -> None:
    """rows: (claim_id, statement)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
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
        """
    )
    for cid, statement in rows:
        db.execute(
            "INSERT INTO claim_fts(claim_id, statement, abstract, body, taxonomy) "
            "VALUES (?, ?, '', '', '')",
            (cid, statement),
        )
    db.commit()
    db.close()


def _seed_vectors(cfg: Config, vectors: dict[str, list[float]]) -> None:
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=len(next(iter(vectors.values()))))
        for id_, v in vectors.items():
            store.upsert("claim", id_, v)


@pytest.fixture()
def hybrid_cfg(tmp_path):
    """Seed a corpus where BM25 misses a paraphrase but vectors nail it."""
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    _seed_fts(
        cfg.fts_path,
        rows=[
            ("clm_target", "Self-attention computes weighted sums across tokens."),
            ("clm_noise_1", "Layer normalization stabilizes training."),
            ("clm_noise_2", "Residual connections help gradient flow."),
        ],
    )
    target = _unit([1.0, 0.0, 0.0])
    _seed_vectors(
        cfg,
        vectors={
            "clm_target": target,
            "clm_noise_1": _unit([0.0, 1.0, 0.0]),
            "clm_noise_2": _unit([0.0, 0.0, 1.0]),
        },
    )
    # Query paraphrase that shares no tokens with clm_target's statement.
    query = "dot product mixing of sequence positions"
    embedder = CannedEmbedder({query: target}, dim=3)
    return cfg, query, embedder


def test_hybrid_surfaces_paraphrase_that_bm25_alone_misses(hybrid_cfg):
    cfg, query, embedder = hybrid_cfg
    bm25_hits = BM25Retriever(cfg).search(query, k=5, scope="claims")
    bm25_ids = [h.id for h in bm25_hits]
    assert "clm_target" not in bm25_ids  # baseline: BM25 fails

    retriever = HybridRetriever(cfg, embedder=embedder)
    hits = retriever.search(query, k=5, scope="claims")
    assert hits[0].id == "clm_target"
    assert hits[0].matched_field.startswith("hybrid")


def test_make_retriever_default_degrades_to_bm25_without_vectors(tmp_path, monkeypatch):
    # v2.1: default habits.retrieval.mode is "hybrid", but when no
    # vectors.sqlite exists the factory must still degrade to BM25.
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    r = make_retriever(cfg)
    assert isinstance(r, BM25Retriever)


def test_make_retriever_hybrid_when_mode_and_vectors_exist(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    # Write habits with hybrid mode.
    save_habits(cfg, Habits(retrieval=RetrievalHabits(mode="hybrid")))
    # Create vectors.sqlite so factory trusts the mode.
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)

    # Factory path calls embedder factory; provide a fake via monkeypatch.
    from second_brain.index import vector_retriever as vr

    monkeypatch.setattr(
        vr,
        "_default_embedder_factory",
        lambda _cfg: CannedEmbedder({}, dim=3),
    )
    r = make_retriever(cfg)
    assert isinstance(r, HybridRetriever)


def test_make_retriever_falls_back_to_bm25_when_vectors_missing(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    save_habits(cfg, Habits(retrieval=RetrievalHabits(mode="hybrid")))
    # vectors.sqlite intentionally absent
    assert not cfg.vectors_path.exists()

    r = make_retriever(cfg)
    assert isinstance(r, BM25Retriever)


def test_hybrid_retriever_passes_through_when_one_side_empty(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    _seed_fts(cfg.fts_path, rows=[("clm_only_bm25", "attention is all you need")])
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)

    embedder = CannedEmbedder({"attention": _unit([1.0, 0.0, 0.0])}, dim=3)
    r = HybridRetriever(cfg, embedder=embedder)
    hits = r.search("attention", k=3, scope="claims")
    assert [h.id for h in hits] == ["clm_only_bm25"]
