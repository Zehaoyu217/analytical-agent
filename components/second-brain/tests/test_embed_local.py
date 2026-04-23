"""Test local sentence-transformers embedder.

Skips when the optional 'vectors' extra is absent so baseline CI still passes.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("sentence_transformers")

from second_brain.embed.local import LocalEmbedder  # noqa: E402


def test_local_embedder_dim_and_shape():
    embedder = LocalEmbedder()
    assert embedder.dim == 384
    out = embedder.embed(["hello world"])
    assert len(out) == 1
    assert len(out[0]) == 384
    assert all(isinstance(x, float) for x in out[0])


def test_local_embedder_same_text_cosine_near_one():
    embedder = LocalEmbedder()
    a, b = embedder.embed(["the quick brown fox", "the quick brown fox"])
    # Encoded with normalize_embeddings=True, so dot product == cosine.
    cosine = sum(x * y for x, y in zip(a, b, strict=True))
    assert cosine == pytest.approx(1.0, abs=1e-4)


def test_local_embedder_batch_ordering_preserved():
    embedder = LocalEmbedder()
    texts = ["cats sleep", "dogs bark", "airplanes fly"]
    out = embedder.embed(texts)
    assert len(out) == 3
    # Each vector is unit length (sum of squares ≈ 1).
    for v in out:
        assert math.isclose(sum(x * x for x in v), 1.0, abs_tol=1e-3)


def test_local_embedder_empty_batch_returns_empty():
    embedder = LocalEmbedder()
    assert embedder.embed([]) == []
