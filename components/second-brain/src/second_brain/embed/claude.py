"""Cloud Claude-family embedder with a hermetic fake-client pattern.

Anthropic does not currently ship a native embeddings endpoint, so this
module is built around the same fake-client contract used by
``second_brain.extract.client``: tests point
``SB_EMBED_FAKE_RESPONSE`` at a JSON file holding canned embeddings.

Live mode is intentionally narrow — if you wire a real embeddings provider
(Voyage, OpenAI, etc.), implement ``_live_embed`` and ship it behind a
feature flag. Until then, the class refuses to silently hit the network.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from second_brain.embed.base import EmbeddingVector

SB_EMBED_FAKE_RESPONSE_ENV = "SB_EMBED_FAKE_RESPONSE"
_DEFAULT_DIM = 1024  # Typical production embedding dim; tests may override.


class ClaudeEmbedderError(RuntimeError):
    """Raised when the Claude embedder cannot produce embeddings."""


class ClaudeEmbedder:
    """Claude-family embedder.

    Behavior:
      - If ``SB_EMBED_FAKE_RESPONSE`` is set, read the file as JSON of shape
        ``{"embeddings": [[...], [...]]}`` and return it verbatim (after
        shape + dim validation).
      - Otherwise, require ``ANTHROPIC_API_KEY`` and call the live path
        (``_live_embed``) which currently raises until a provider is wired.
    """

    def __init__(self, *, model: str = "claude-embed-v1", dim: int = _DEFAULT_DIM) -> None:
        self.model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[EmbeddingVector]:
        if not texts:
            return []
        fake_path = os.environ.get(SB_EMBED_FAKE_RESPONSE_ENV)
        if fake_path:
            return self._load_fake(Path(fake_path), expected=len(texts))
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ClaudeEmbedderError(
                "ClaudeEmbedder requires either "
                f"${SB_EMBED_FAKE_RESPONSE_ENV} (for tests) or "
                "$ANTHROPIC_API_KEY (for live calls)."
            )
        return self._live_embed(texts)

    def _load_fake(self, path: Path, *, expected: int) -> list[EmbeddingVector]:
        if not path.exists():
            raise ClaudeEmbedderError(f"fake payload not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ClaudeEmbedderError(f"fake payload not valid JSON: {exc}") from exc
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list):
            raise ClaudeEmbedderError("fake payload missing 'embeddings' list")
        if len(embeddings) != expected:
            raise ClaudeEmbedderError(
                f"fake payload has {len(embeddings)} rows but {expected} texts were embedded"
            )
        out: list[EmbeddingVector] = []
        for row in embeddings:
            if not isinstance(row, list):
                raise ClaudeEmbedderError("fake payload rows must be lists of floats")
            if len(row) != self.dim:
                raise ClaudeEmbedderError(
                    f"fake payload vector dim={len(row)} but embedder.dim={self.dim}"
                )
            out.append([float(x) for x in row])
        return out

    def _live_embed(self, texts: list[str]) -> list[EmbeddingVector]:  # pragma: no cover
        # Intentionally unimplemented: Anthropic does not expose a native
        # embeddings endpoint as of writing. Swap this out for Voyage,
        # OpenAI, or whatever provider you choose once the decision is made.
        raise ClaudeEmbedderError(
            "ClaudeEmbedder live mode not implemented. "
            f"Set ${SB_EMBED_FAKE_RESPONSE_ENV} or wire a real provider."
        )
