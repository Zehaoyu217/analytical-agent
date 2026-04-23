"""Embedder Protocol + shared type aliases."""
from __future__ import annotations

from typing import Protocol

EmbeddingVector = list[float]


class Embedder(Protocol):
    """Minimal duck-typed contract for embedding backends.

    Implementations MUST:
      - expose ``dim`` (length of every returned vector).
      - be deterministic per-text within a single process.
      - preserve input order in the returned list.
    """

    dim: int

    def embed(self, texts: list[str]) -> list[EmbeddingVector]: ...
