"""Local sentence-transformers embedder (default model: all-MiniLM-L6-v2)."""
from __future__ import annotations

from functools import cached_property

from second_brain.embed.base import EmbeddingVector

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_DIM = 384


class LocalEmbedder:
    """Wraps sentence-transformers with ``normalize_embeddings=True``.

    The model is lazily loaded on first ``embed`` call so constructor stays
    cheap and tests that only touch the protocol don't pay the import cost.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL, dim: int = _DEFAULT_DIM) -> None:
        self.model_name = model_name
        self.dim = dim

    @cached_property
    def _model(self):  # noqa: ANN202 — sentence_transformers type is heavy; lazy.
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        return SentenceTransformer(self.model_name)

    def embed(self, texts: list[str]) -> list[EmbeddingVector]:
        if not texts:
            return []
        arr = self._model.encode(texts, normalize_embeddings=True)
        # sentence-transformers returns ndarray; normalize to plain lists.
        return [[float(x) for x in row] for row in arr]
