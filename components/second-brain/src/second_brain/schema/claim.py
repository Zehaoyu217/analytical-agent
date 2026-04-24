from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimKind(StrEnum):
    EMPIRICAL = "empirical"
    THEORETICAL = "theoretical"
    DEFINITIONAL = "definitional"
    OPINION = "opinion"
    PREDICTION = "prediction"


class ClaimConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClaimStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
    DISPUTED = "disputed"


class ClaimFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    statement: str
    kind: ClaimKind
    confidence: ClaimConfidence
    scope: str = ""
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    refines: list[str] = Field(default_factory=list)
    extracted_at: datetime
    status: ClaimStatus = ClaimStatus.ACTIVE
    resolution: str | None = None
    abstract: str = ""
    # Supersession chain. ``supersedes`` lists older claim ids that this
    # claim replaces; ``superseded_by`` points at the newer claim that
    # replaces *this* one. Retrieval default-excludes claims with a
    # non-null ``superseded_by`` so the agent never quotes a stale
    # assertion after a paper is revised or a finding is refined.
    supersedes: list[str] = Field(default_factory=list)
    superseded_by: str | None = None

    @field_validator("id")
    @classmethod
    def _id_prefix(cls, v: str) -> str:
        if not v.startswith("clm_"):
            raise ValueError("id must start with 'clm_'")
        return v

    def to_frontmatter_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_frontmatter_dict(cls, data: dict[str, Any]) -> ClaimFrontmatter:
        return cls.model_validate(data)
