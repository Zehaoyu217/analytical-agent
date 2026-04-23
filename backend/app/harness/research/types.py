from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PaperFinding:
    title: str
    key_finding: str          # one sentence: result + recipe
    source: Literal["hf_papers", "semantic_scholar", "arxiv"]
    arxiv_id: str | None = None
    year: int | None = None
    citation_count: int | None = None
    section_excerpts: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PapersResult:
    papers: tuple[PaperFinding, ...] = field(default_factory=tuple)
    crawl_depth: int = 0


@dataclass(frozen=True)
class CodeExample:
    url: str
    repo: str
    file_path: str
    snippet: str              # ≤500 chars
    relevance: str            # one sentence
    stars: int | None = None


@dataclass(frozen=True)
class CodeResult:
    examples: tuple[CodeExample, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WebPage:
    url: str
    title: str
    summary: str              # ≤300 chars


@dataclass(frozen=True)
class WebResult:
    pages: tuple[WebPage, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RoutePlan:
    modules: tuple[str, ...]
    sub_queries: dict[str, str]
    budgets: dict[str, int]
    parallel_ok: bool
    rationale: str


@dataclass(frozen=True)
class ResearchResult:
    summary: str
    papers: tuple[PaperFinding, ...]
    code_examples: tuple[CodeExample, ...]
    web_refs: tuple[WebPage, ...]
    follow_up_questions: tuple[str, ...]
    modules_ran: tuple[str, ...]
    total_ms: int
    budget_tokens_used: int
    budget_warning: str | None = None
