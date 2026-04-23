"""Tests for sqlite-vec VectorStore."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("sqlite_vec")

from second_brain.config import Config  # noqa: E402
from second_brain.index.vector_store import VectorStore  # noqa: E402


def _unit(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]


def test_vectors_path_on_config(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    assert cfg.vectors_path == tmp_path / ".sb" / "vectors.sqlite"


def test_upsert_and_topk_cosine_order(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)

    # Craft three orthogonal-ish vectors, then add a fourth close to the first.
    vectors = {
        "clm_a": _unit([1.0, 0.0, 0.0]),
        "clm_b": _unit([0.0, 1.0, 0.0]),
        "clm_c": _unit([0.0, 0.0, 1.0]),
        "clm_a2": _unit([0.95, 0.05, 0.0]),
    }
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        for id_, v in vectors.items():
            store.upsert("claim", id_, v)

    with VectorStore.open(cfg.vectors_path) as store:
        hits = store.topk("claim", _unit([1.0, 0.0, 0.0]), k=3)
    assert [h[0] for h in hits[:2]] == ["clm_a", "clm_a2"]
    # Distances should be monotonically non-decreasing.
    distances = [d for _, d in hits]
    assert distances == sorted(distances)


def test_upsert_replaces_existing(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        store.upsert("claim", "clm_x", _unit([1.0, 0.0, 0.0]))
        store.upsert("claim", "clm_x", _unit([0.0, 1.0, 0.0]))

    with VectorStore.open(cfg.vectors_path) as store:
        hits = store.topk("claim", _unit([0.0, 1.0, 0.0]), k=1)
    assert hits[0][0] == "clm_x"
    # Distance near zero means the second upsert won.
    assert hits[0][1] < 0.1


def test_topk_with_k_larger_than_corpus(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        store.upsert("claim", "clm_only", _unit([1.0, 0.0, 0.0]))
        hits = store.topk("claim", _unit([1.0, 0.0, 0.0]), k=50)
    assert len(hits) == 1


def test_topk_on_empty_table(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        hits = store.topk("claim", _unit([1.0, 0.0, 0.0]), k=5)
    assert hits == []


def test_source_and_claim_tables_isolated(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        store.upsert("claim", "clm_a", _unit([1.0, 0.0, 0.0]))
        store.upsert("source", "src_a", _unit([0.0, 1.0, 0.0]))
        claim_hits = store.topk("claim", _unit([1.0, 0.0, 0.0]), k=10)
        source_hits = store.topk("source", _unit([0.0, 1.0, 0.0]), k=10)
    assert [h[0] for h in claim_hits] == ["clm_a"]
    assert [h[0] for h in source_hits] == ["src_a"]


def test_ensure_schema_with_different_dim_is_rejected(tmp_path):
    cfg = Config(home=tmp_path, sb_dir=tmp_path / ".sb")
    cfg.sb_dir.mkdir(parents=True)
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
    with VectorStore.open(cfg.vectors_path) as store, pytest.raises(ValueError):
        store.ensure_schema(dim=5)
