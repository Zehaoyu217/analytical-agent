"""Gardener LLM passes.

Each pass conforms to :class:`second_brain.gardener.protocol.GardenerPass`:
``estimate(cfg, habits) -> PassEstimate`` for pre-flight cost, and
``run(cfg, habits, client, budget) -> Iterable[Proposal]`` for execution.
"""
from __future__ import annotations

from second_brain.gardener.passes.contradict import ContradictPass
from second_brain.gardener.passes.dedupe import DedupePass
from second_brain.gardener.passes.extract import ExtractPass
from second_brain.gardener.passes.re_abstract import ReAbstractPass
from second_brain.gardener.passes.semantic_link import SemanticLinkPass
from second_brain.gardener.passes.taxonomy_curate import TaxonomyCuratePass
from second_brain.gardener.passes.wiki_summarize import WikiSummarizePass

__all__ = [
    "ContradictPass",
    "DedupePass",
    "ExtractPass",
    "ReAbstractPass",
    "SemanticLinkPass",
    "TaxonomyCuratePass",
    "WikiSummarizePass",
]
