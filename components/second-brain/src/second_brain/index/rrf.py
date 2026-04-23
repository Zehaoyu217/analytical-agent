"""Reciprocal Rank Fusion — a pure, boring function.

RRF assigns ``1 / (k + rank + 1)`` to every id for each list it appears in,
then sums across lists. Empirically robust across retrieval tasks and
requires no score calibration between the fused retrievers.
"""
from __future__ import annotations


def rrf_fuse(
    lists: list[list[str]],
    k_rrf: int = 60,
) -> list[tuple[str, float]]:
    """Fuse ranked id lists into a single ranked list.

    Args:
        lists: each inner list is an ordered sequence of ids, best first.
        k_rrf: dampening constant (Cormack et al. 2009 use 60).

    Returns:
        ``[(id, score), ...]`` sorted by score desc.
    """
    scores: dict[str, float] = {}
    for ranked in lists:
        for rank, id_ in enumerate(ranked):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k_rrf + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
