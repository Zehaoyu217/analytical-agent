"""Tests for ``reindex(cfg, with_vectors=True)`` populating vectors.sqlite."""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pytest
from ruamel.yaml import YAML

pytest.importorskip("sqlite_vec")

from second_brain.config import Config  # noqa: E402
from second_brain.index.vector_store import VectorStore  # noqa: E402
from second_brain.reindex import reindex  # noqa: E402
from second_brain.schema.claim import (  # noqa: E402
    ClaimConfidence,
    ClaimFrontmatter,
    ClaimKind,
)


def _dump_yaml(data: dict) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    buf = StringIO()
    yaml.dump(data, buf)
    return buf.getvalue().rstrip()


def _write_claim(cfg: Config, claim_id: str, statement: str) -> None:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    fm = ClaimFrontmatter(
        id=claim_id,
        statement=statement,
        kind=ClaimKind.EMPIRICAL,
        confidence=ClaimConfidence.MEDIUM,
        extracted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        abstract=statement,
    )
    path = cfg.claims_dir / f"{claim_id}.md"
    path.write_text(
        "---\n" + _dump_yaml(fm.to_frontmatter_dict()) + "\n---\n\n" + statement,
        encoding="utf-8",
    )


class StubEmbedder:
    """Produces a deterministic dim-3 vector per text."""

    def __init__(self, mapping: dict[str, list[float]], dim: int = 3) -> None:
        self.mapping = mapping
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if t in self.mapping:
                out.append(self.mapping[t])
            else:
                # stable fallback: hash to a unit vector in R^3
                h = sum(ord(c) for c in t) or 1
                v = [((h >> i) & 0xF) / 16.0 for i in range(3)]
                mag = sum(x * x for x in v) ** 0.5 or 1.0
                out.append([x / mag for x in v])
        return out


def test_reindex_with_vectors_populates_store(tmp_path: Path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    _write_claim(cfg, "clm_attention", "Self-attention weighted sum")
    _write_claim(cfg, "clm_layernorm", "Layer norm stabilizes gradients")

    target_vec = [1.0, 0.0, 0.0]
    embedder = StubEmbedder(
        {
            "Self-attention weighted sum": target_vec,
            "Layer norm stabilizes gradients": [0.0, 1.0, 0.0],
        }
    )

    reindex(cfg, with_vectors=True, embedder=embedder)

    assert cfg.vectors_path.exists()
    with VectorStore.open(cfg.vectors_path) as store:
        hits = store.topk("claim", target_vec, k=5)
    ids = [h[0] for h in hits]
    assert ids[0] == "clm_attention"
    assert "clm_layernorm" in ids


def test_reindex_without_vectors_leaves_store_absent(tmp_path: Path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    _write_claim(cfg, "clm_x", "something")

    reindex(cfg)  # with_vectors defaults to False
    assert not cfg.vectors_path.exists()


def test_reindex_with_vectors_resilient_to_batch_failure(
    tmp_path: Path, monkeypatch, caplog
):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    _write_claim(cfg, "clm_ok", "ok claim")
    _write_claim(cfg, "clm_bad", "bad claim")

    class FlakeyEmbedder:
        dim = 3

        def embed(self, texts: list[str]) -> list[list[float]]:
            if any("bad" in t for t in texts):
                raise RuntimeError("embedding provider exploded")
            return [[1.0, 0.0, 0.0]] * len(texts)

    # Should not raise even though one batch fails.
    reindex(cfg, with_vectors=True, embedder=FlakeyEmbedder(), vector_batch_size=1)
    assert cfg.vectors_path.exists()
    with VectorStore.open(cfg.vectors_path) as store:
        hits = store.topk("claim", [1.0, 0.0, 0.0], k=10)
    ids = {h[0] for h in hits}
    assert "clm_ok" in ids
    assert "clm_bad" not in ids
