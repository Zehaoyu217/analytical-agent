from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.index.retriever import RetrievalHit
from second_brain.inject.renderer import render_injection_block
from second_brain.research.broker import broker_search, render_broker_block


class _RetrieverProto(Protocol):
    def search(self, query: str, k: int = 10, scope: str = "both",
               taxonomy: str | None = None,
               with_neighbors: bool = False) -> list[RetrievalHit]: ...


@dataclass(frozen=True)
class InjectionResult:
    block: str
    hit_ids: list[str]
    skipped_reason: str | None = None


def _matches_any(prompt: str, patterns: list[str]) -> bool:
    for pat in patterns:
        try:
            if re.search(pat, prompt):
                return True
        except re.error:
            # A malformed habit regex should never block the agent — treat as no-match.
            continue
    return False


def _default_retriever(cfg: Config) -> _RetrieverProto:
    from second_brain.index.retriever import BM25Retriever
    return BM25Retriever(cfg)


def build_injection(
    cfg: Config,
    habits: Habits,
    prompt: str,
    *,
    retriever: _RetrieverProto | None = None,
) -> InjectionResult:
    inj = habits.injection
    if not inj.enabled:
        return InjectionResult(block="", hit_ids=[], skipped_reason="disabled")

    if _matches_any(prompt, inj.skip_patterns):
        return InjectionResult(block="", hit_ids=[], skipped_reason="skip_pattern")

    if retriever is None:
        broker_result = broker_search(cfg, query=prompt, k=inj.k, scope="both")
        if not broker_result.hits:
            return InjectionResult(block="", hit_ids=[], skipped_reason="no_hits")
        if broker_result.hits[0].score < inj.min_score:
            return InjectionResult(block="", hit_ids=[], skipped_reason="below_min_score")
        block = render_broker_block(broker_result.hits, max_tokens=inj.max_tokens)
        return InjectionResult(
            block=block,
            hit_ids=[h.id for h in broker_result.hits],
        )

    hits = retriever.search(prompt, k=inj.k, scope="claims")
    if not hits:
        return InjectionResult(block="", hit_ids=[], skipped_reason="no_hits")

    if hits[0].score < inj.min_score:
        return InjectionResult(block="", hit_ids=[], skipped_reason="below_min_score")

    block = render_injection_block(hits, max_tokens=inj.max_tokens)
    return InjectionResult(block=block, hit_ids=[h.id for h in hits])
