from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AutonomyMode = Literal["auto", "hitl"]
Density = Literal["sparse", "moderate", "dense"]
RetrievalPref = Literal["claims", "sources", "balanced"]
RetrievalScope = Literal["claims", "sources", "both"]
RetrievalMode = Literal["bm25", "hybrid"]
EmbeddingModel = Literal["local", "claude"]


class NamingConvention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_slug: str = "{kind-prefix}_{year?}_{title-kebab}"
    claim_slug: str = "{verb}-{subject-kebab}"
    max_slug_length: int = 80


class TaxonomyHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    roots: list[str] = Field(
        default_factory=lambda: [
            "papers/ml", "papers/systems", "blog", "news",
            "notes/personal", "notes/work", "repos/ml", "repos/infra",
        ]
    )
    enforce: Literal["soft", "strict"] = "soft"


class ExtractionConfidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    require_quote_for_extracted: bool = True
    max_inferred_per_source: int = 20


class ExtractionHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    default_density: Density = "moderate"
    by_taxonomy: dict[str, Density] = Field(
        default_factory=lambda: {
            "papers/*": "dense",
            "blog/*": "sparse",
            "news/*": "sparse",
            "notes/*": "moderate",
            "repos/*": "sparse",
        }
    )
    by_kind: dict[str, Density] = Field(default_factory=lambda: {"url": "sparse"})
    claim_rubric: str = (
        "A claim is an atomic, falsifiable assertion. Skip rhetoric, background.\n"
        "Prefer author's exact phrasing. Tag `kind: opinion` when scope is limited."
    )
    confidence_policy: ExtractionConfidencePolicy = Field(default_factory=ExtractionConfidencePolicy)


class RetrievalHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prefer: RetrievalPref = "claims"
    default_k: int = 10
    default_scope: RetrievalScope = "both"
    max_depth_content: int = 1
    # v2.1: defaults to "hybrid"; ``make_retriever`` degrades to BM25 when
    # ``.sb/vectors.sqlite`` is missing, so old clones keep working.
    mode: RetrievalMode = "hybrid"
    embedding_model: EmbeddingModel = "local"
    rrf_k: int = 60


class InjectionHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    k: int = 5
    max_tokens: int = 800
    min_score: float = 0.2
    skip_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^/",
            r"^(git|gh|npm|pip|make)\b",
            r"\b(ssh|curl|docker)\b",
        ]
    )


class ConflictsHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    grace_period_days: int = 14
    cluster_threshold: int = 3


class RepoCaptureHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    globs: list[str] = Field(
        default_factory=lambda: [
            "README*", "docs/**/*.md", "pyproject.toml", "package.json", "Cargo.toml",
        ]
    )
    exclude_globs: list[str] = Field(
        default_factory=lambda: ["node_modules/**", "target/**", ".git/**"]
    )


class Autonomy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    default: AutonomyMode = "hitl"
    overrides: dict[str, AutonomyMode] = Field(
        default_factory=lambda: {
            "ingest.slug": "auto",
            "ingest.taxonomy": "hitl",
            "extraction.density_adjust": "auto",
            "reconciliation.resolution": "hitl",
            "reconciliation.reject_edge": "auto",
            "habit_learning.apply": "hitl",
        }
    )

    def for_op(self, op: str) -> AutonomyMode:
        return self.overrides.get(op, self.default)


class LearningHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    threshold_overrides: int = 3
    rolling_window_days: int = 90
    dimensions: list[str] = Field(
        default_factory=lambda: [
            "naming.source_slug",
            "naming.claim_slug",
            "taxonomy.roots",
            "extraction.by_taxonomy",
            "extraction.by_kind",
            "injection.skip_patterns",
        ]
    )


class MaintenanceNightly(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    time: str = "03:30"
    tasks: list[str] = Field(
        default_factory=lambda: [
            "lint",
            "regen_abstracts_for_changed",
            "rebuild_conflicts_md",
            "prune_failed_ingests_older_than_30d",
            "habit_learning_detector",
        ]
    )


class MaintenanceHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    nightly: MaintenanceNightly = Field(default_factory=MaintenanceNightly)


class DigestHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = False
    passes: dict[str, bool] = Field(
        default_factory=lambda: {
            "reconciliation": True,
            "wiki_bridge": True,
            "taxonomy_drift": True,
            "stale_review": True,
            "edge_audit": True,
        }
    )
    min_entries_to_emit: int = 0
    skip_ttl_days: int = 14


GardenerMode = Literal["proposal", "autonomous"]


class GardenerHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: GardenerMode = "proposal"
    models: dict[str, str] = Field(
        default_factory=lambda: {
            "cheap": "mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit",
            "default": "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit",
            "deep": "mlx/NexVeridian/gemma-4-26B-A4b-it-4bit",
        }
    )
    passes: dict[str, bool] = Field(
        default_factory=lambda: {
            "extract": True,
            "re_abstract": True,
            "semantic_link": True,
            "dedupe": False,
            "contradict": False,
            "taxonomy_curate": False,
            "wiki_summarize": False,
        }
    )
    max_cost_usd_per_run: float = 0.50
    max_tokens_per_source: int = 8000
    dry_run: bool = False


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = ""
    primary_language: str = "en"


class Habits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: Identity = Field(default_factory=Identity)
    taxonomy: TaxonomyHabits = Field(default_factory=TaxonomyHabits)
    naming_convention: NamingConvention = Field(default_factory=NamingConvention)
    extraction: ExtractionHabits = Field(default_factory=ExtractionHabits)
    retrieval: RetrievalHabits = Field(default_factory=RetrievalHabits)
    injection: InjectionHabits = Field(default_factory=InjectionHabits)
    conflicts: ConflictsHabits = Field(default_factory=ConflictsHabits)
    repo_capture: RepoCaptureHabits = Field(default_factory=RepoCaptureHabits)
    autonomy: Autonomy = Field(default_factory=Autonomy)
    learning: LearningHabits = Field(default_factory=LearningHabits)
    maintenance: MaintenanceHabits = Field(default_factory=MaintenanceHabits)
    digest: DigestHabits = Field(default_factory=DigestHabits)
    gardener: GardenerHabits = Field(default_factory=GardenerHabits)

    @classmethod
    def default(cls) -> Habits:
        return cls()
