"""Retrieval eval suite: nDCG@10 over an FTS-seeded claim corpus.

Fixture: ``seed.yaml`` with ``claims`` + ``queries``. The suite wipes
``cfg.fts_path`` and re-seeds it from the fixture claims, so the run is
hermetic and safe to execute against any ``Config`` (including production).
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.eval.runner import EvalCase
from second_brain.index.retriever import BM25Retriever, HybridRetriever
from second_brain.store.fts_store import FtsStore

P95_LATENCY_MS = 100.0

Mode = Literal["bm25", "hybrid", "compare"]

_yaml = YAML(typ="safe")


def _dcg(relevance: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(relevance))


def _ndcg(expected: list[str], got: list[str], k: int = 10) -> float:
    """Normalized DCG over binary relevance labels."""
    relevance = [1 if gid in expected else 0 for gid in got[:k]]
    if not any(relevance):
        return 0.0
    ideal = sorted(relevance, reverse=True)
    dcg = _dcg(relevance)
    idcg = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


def _reseed(cfg: Config, claims: list[dict]) -> None:
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    if cfg.fts_path.exists():
        cfg.fts_path.unlink()
    with FtsStore.open(cfg.fts_path) as store:
        store.ensure_schema()
        for c in claims:
            store.insert_claim(
                claim_id=c["id"],
                statement=c["statement"],
                abstract="",
                body="",
                taxonomy=c.get("taxonomy", ""),
            )


class RetrievalSuite:
    name = "retrieval"

    def __init__(self, mode: Mode = "bm25", embedder=None) -> None:  # noqa: ANN001
        self.mode = mode
        self._embedder = embedder

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        seed = _yaml.load(
            (fixtures_dir / "seed.yaml").read_text(encoding="utf-8")
        )
        _reseed(cfg, seed["claims"])

        if self.mode == "compare":
            return (
                self._run_mode(cfg, seed, "bm25")
                + self._run_mode(cfg, seed, "hybrid")
            )
        return self._run_mode(cfg, seed, self.mode)

    def _run_mode(
        self, cfg: Config, seed: dict, mode: Literal["bm25", "hybrid"]
    ) -> list[EvalCase]:
        retriever = self._build(cfg, mode)
        cases: list[EvalCase] = []
        for q in seed["queries"]:
            t0 = time.monotonic()
            hits = retriever.search(q["query"], k=10, scope="claims")
            latency_ms = (time.monotonic() - t0) * 1000
            got_ids = [h.id for h in hits]
            ndcg = _ndcg(q["expected_ids"], got_ids, k=10)
            passed = ndcg >= q["min_ndcg"] and latency_ms < P95_LATENCY_MS
            cases.append(
                EvalCase(
                    name=f"[{mode}] {q['query']}",
                    passed=passed,
                    metric=ndcg,
                    details=(
                        f"mode={mode} nDCG={ndcg:.3f} latency={latency_ms:.1f}ms "
                        f"hits={got_ids[:3]}"
                    ),
                )
            )
        return cases

    def _build(self, cfg: Config, mode: str):  # noqa: ANN202
        if mode == "hybrid":
            if self._embedder is not None:
                return HybridRetriever(cfg, embedder=self._embedder)
            return HybridRetriever(cfg)
        return BM25Retriever(cfg)
