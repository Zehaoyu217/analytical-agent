from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EXTENSION_TAG = "cca-v1"
ExtractorName = Literal["fastapi_routes", "intra_file_calls", "jsx_usage"]


@dataclass(frozen=True)
class ExtractedNode:
    id: str
    label: str
    file_type: str  # "code" | "route"
    source_file: str
    source_location: int | None
    extractor: ExtractorName


@dataclass(frozen=True)
class ExtractedEdge:
    source: str
    target: str
    relation: str  # "routes_to" | "calls" | "uses"
    source_file: str
    source_location: int | None
    extractor: ExtractorName
    confidence: str = "EXTRACTED"
    confidence_score: float = 1.0


@dataclass(frozen=True)
class ExtractionResult:
    nodes: list[ExtractedNode] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
