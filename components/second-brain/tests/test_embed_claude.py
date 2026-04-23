"""Test Claude cloud embedder with hermetic fake-client pattern."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from second_brain.embed.claude import (
    SB_EMBED_FAKE_RESPONSE_ENV,
    ClaudeEmbedder,
    ClaudeEmbedderError,
)


def _write_fake(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "fake.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_claude_embedder_uses_fake_payload(tmp_path, monkeypatch):
    payload = {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}
    p = _write_fake(tmp_path, payload)
    monkeypatch.setenv(SB_EMBED_FAKE_RESPONSE_ENV, str(p))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    embedder = ClaudeEmbedder(dim=3)
    out = embedder.embed(["one", "two"])
    assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert embedder.dim == 3


def test_claude_embedder_raises_when_no_fake_and_no_key(monkeypatch):
    monkeypatch.delenv(SB_EMBED_FAKE_RESPONSE_ENV, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    embedder = ClaudeEmbedder(dim=3)
    with pytest.raises(ClaudeEmbedderError):
        embedder.embed(["anything"])


def test_claude_embedder_empty_batch_returns_empty(tmp_path, monkeypatch):
    # Should not even touch the fake payload / API.
    monkeypatch.delenv(SB_EMBED_FAKE_RESPONSE_ENV, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    embedder = ClaudeEmbedder(dim=3)
    assert embedder.embed([]) == []


def test_claude_embedder_validates_fake_payload_shape(tmp_path, monkeypatch):
    bad = _write_fake(tmp_path, {"embeddings": [[0.1, 0.2]]})  # only one row for two texts
    monkeypatch.setenv(SB_EMBED_FAKE_RESPONSE_ENV, str(bad))

    embedder = ClaudeEmbedder(dim=2)
    with pytest.raises(ClaudeEmbedderError):
        embedder.embed(["a", "b"])


def test_claude_embedder_validates_vector_dim(tmp_path, monkeypatch):
    bad = _write_fake(tmp_path, {"embeddings": [[0.1, 0.2, 0.3, 0.4]]})  # dim=4 but we declared 3
    monkeypatch.setenv(SB_EMBED_FAKE_RESPONSE_ENV, str(bad))

    embedder = ClaudeEmbedder(dim=3)
    with pytest.raises(ClaudeEmbedderError):
        embedder.embed(["a"])
