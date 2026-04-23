from __future__ import annotations

from enum import StrEnum


class RelationType(StrEnum):
    CITES = "cites"
    RELATED = "related"
    SUPERSEDES = "supersedes"
    SUPPORTS = "supports"
    EVIDENCED_BY = "evidenced_by"
    CONTRADICTS = "contradicts"
    REFINES = "refines"
    IN_PROJECT = "in_project"
    INFORMS_PAPER = "informs_paper"
    TESTS_CLAIM = "tests_claim"
    USES_SOURCE = "uses_source"
    SYNTHESIZES = "synthesizes"


class EdgeConfidence(StrEnum):
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    AMBIGUOUS = "ambiguous"


SOURCE_TO_SOURCE: frozenset[RelationType] = frozenset(
    {RelationType.CITES, RelationType.RELATED, RelationType.SUPERSEDES}
)
CLAIM_TO_SOURCE: frozenset[RelationType] = frozenset(
    {RelationType.SUPPORTS, RelationType.EVIDENCED_BY}
)
CLAIM_TO_CLAIM: frozenset[RelationType] = frozenset(
    {RelationType.CONTRADICTS, RelationType.REFINES}
)
