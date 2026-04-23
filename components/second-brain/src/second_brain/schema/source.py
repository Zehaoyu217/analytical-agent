from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceKind(StrEnum):
    PDF = "pdf"
    URL = "url"
    REPO = "repo"
    NOTE = "note"
    DOCX = "docx"
    EPUB = "epub"
    FAILED = "failed"


class RawArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    kind: str = "original"
    sha256: str | None = None


class SourceFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    title: str
    kind: SourceKind
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    ingested_at: datetime
    content_hash: str
    habit_taxonomy: str | None = None
    raw: list[RawArtifact] = Field(default_factory=list)
    cites: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    abstract: str = ""

    @field_validator("id")
    @classmethod
    def _id_prefix(cls, v: str) -> str:
        if not v.startswith("src_"):
            raise ValueError("id must start with 'src_'")
        return v

    def to_frontmatter_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_frontmatter_dict(cls, data: dict[str, Any]) -> SourceFrontmatter:
        return cls.model_validate(data)
