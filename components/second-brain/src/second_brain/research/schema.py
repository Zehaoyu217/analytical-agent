from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document


class CenterKind(StrEnum):
    PAPER = "paper"
    PROJECT = "project"
    EXPERIMENT = "experiment"
    SYNTHESIS = "synthesis"


class CenterStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CONFLICTED = "conflicted"
    STALE = "stale"
    SUPERSEDED = "superseded"


class CenterFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    kind: CenterKind
    title: str
    status: CenterStatus = CenterStatus.PUBLISHED
    summary: str = ""
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.8
    project_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    synthesis_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    updated_at: datetime

    @field_validator("id")
    @classmethod
    def _id_must_have_prefix(cls, value: str) -> str:
        if "_" not in value:
            raise ValueError("center ids must use a typed prefix")
        return value

    def to_frontmatter_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class PaperFrontmatter(CenterFrontmatter):
    kind: Literal[CenterKind.PAPER] = CenterKind.PAPER
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    source_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class ProjectFrontmatter(CenterFrontmatter):
    kind: Literal[CenterKind.PROJECT] = CenterKind.PROJECT
    question: str = ""
    objective: str = ""
    keywords: list[str] = Field(default_factory=list)
    active: bool = True
    paper_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    synthesis_ids: list[str] = Field(default_factory=list)


class ExperimentFrontmatter(CenterFrontmatter):
    kind: Literal[CenterKind.EXPERIMENT] = CenterKind.EXPERIMENT
    run_id: str = ""
    hypothesis: str = ""
    result_summary: str = ""
    decision: str = ""
    metric_summary: dict[str, float | int | str] = Field(default_factory=dict)


class SynthesisFrontmatter(CenterFrontmatter):
    kind: Literal[CenterKind.SYNTHESIS] = CenterKind.SYNTHESIS
    question: str = ""
    scope: str = ""
    decision_state: str = ""


CenterDocument = PaperFrontmatter | ProjectFrontmatter | ExperimentFrontmatter | SynthesisFrontmatter

_CENTER_TYPES: dict[str, type[CenterDocument]] = {
    CenterKind.PAPER.value: PaperFrontmatter,
    CenterKind.PROJECT.value: ProjectFrontmatter,
    CenterKind.EXPERIMENT.value: ExperimentFrontmatter,
    CenterKind.SYNTHESIS.value: SynthesisFrontmatter,
}


def center_dir_for_kind(cfg: Config, kind: CenterKind) -> Path:
    if kind == CenterKind.PAPER:
        return cfg.papers_dir
    if kind == CenterKind.PROJECT:
        return cfg.projects_dir
    if kind == CenterKind.EXPERIMENT:
        return cfg.experiments_dir
    if kind == CenterKind.SYNTHESIS:
        return cfg.syntheses_dir
    raise ValueError(f"unsupported center kind: {kind}")


def load_center_document(path: Path) -> tuple[CenterDocument, str]:
    meta, body = load_document(path)
    kind = str(meta.get("kind", ""))
    model = _CENTER_TYPES.get(kind)
    if model is None:
        raise ValueError(f"{path}: unsupported center kind {kind!r}")
    return model.model_validate(meta), body


def dump_center_document(path: Path, meta: CenterDocument, body: str) -> None:
    dump_document(path, meta.to_frontmatter_dict(), body)


def iter_center_documents(cfg: Config) -> list[tuple[Path, CenterDocument, str]]:
    out: list[tuple[Path, CenterDocument, str]] = []
    for root in (cfg.papers_dir, cfg.projects_dir, cfg.experiments_dir, cfg.syntheses_dir):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            doc, body = load_center_document(path)
            out.append((path, doc, body))
    return out
