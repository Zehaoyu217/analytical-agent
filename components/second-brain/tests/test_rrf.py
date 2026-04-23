"""Tests for Reciprocal Rank Fusion helper."""
from __future__ import annotations

import pytest

from second_brain.index.rrf import rrf_fuse


def test_single_list_preserves_order():
    fused = rrf_fuse([["a", "b", "c"]])
    assert [id_ for id_, _ in fused] == ["a", "b", "c"]


def test_two_lists_merge_common_ids_higher():
    # "b" appears high in both lists; should outrank "a" (top of list 1 only)
    # because its two contributions add up.
    fused = rrf_fuse(
        [
            ["a", "b", "c"],
            ["b", "d", "a"],
        ],
        k_rrf=60,
    )
    ids = [id_ for id_, _ in fused]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c", "d"}


def test_unknown_ids_from_one_list_still_included():
    fused = rrf_fuse([["a"], ["b"]])
    assert {id_ for id_, _ in fused} == {"a", "b"}


def test_empty_input_returns_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_scores_are_positive_and_descending():
    fused = rrf_fuse([["a", "b", "c"], ["c", "b", "a"]])
    scores = [s for _, s in fused]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_k_rrf_controls_score_magnitude():
    low = rrf_fuse([["a"]], k_rrf=1)
    high = rrf_fuse([["a"]], k_rrf=1000)
    # Same top id, but smaller k_rrf should give a larger score.
    assert low[0][0] == "a" == high[0][0]
    assert low[0][1] > high[0][1]


def test_property_top_hit_is_id_with_best_aggregate_rank():
    # "x" is rank 0 in both lists → best aggregate; should always win.
    lists = [["x", "y", "z"], ["x", "a", "b"]]
    fused = rrf_fuse(lists)
    assert fused[0][0] == "x"


def test_ties_are_stable_to_insertion():
    # Two ids appear only in one list each at the same rank → identical RRF score.
    fused = rrf_fuse([["a"], ["b"]])
    assert len(fused) == 2
    assert fused[0][1] == pytest.approx(fused[1][1])
