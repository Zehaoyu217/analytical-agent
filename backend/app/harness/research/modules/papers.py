from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

import httpx

from app.harness.research.types import PaperFinding, PapersResult

logger = logging.getLogger(__name__)

_HF_API = "https://huggingface.co/api/papers"
_S2_API = "https://api.semanticscholar.org/graph/v1"
_ARXIV_API = "https://export.arxiv.org/api/query"

_RECENCY_SIGNALS = frozenset({
    "recent", "new", "latest", "2024", "2025", "2026", "state of the art", "sota",
})
_S2_TIMEOUT = 12
_BUDGET_MIN = 1_000


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _recency_query(query: str) -> bool:
    lower = query.lower()
    return any(sig in lower for sig in _RECENCY_SIGNALS)


@dataclass
class _RawPaper:
    title: str
    arxiv_id: str | None
    year: str | int | None   # HF path yields "2025" (str); S2/ArXiv yield int
    citation_count: int | None
    abstract: str
    source: str


class PapersModule:
    """Searches HF Papers, Semantic Scholar, and ArXiv for relevant papers."""

    def __init__(self) -> None:
        self._s2_headers: dict[str, str] = {}
        api_key = os.environ.get("S2_API_KEY")
        if api_key:
            self._s2_headers["x-api-key"] = api_key

    def run(self, query: str, budget_tokens: int) -> PapersResult:
        if budget_tokens < _BUDGET_MIN:
            return PapersResult()

        papers: list[PaperFinding] = []
        tokens_used = 0
        crawl_depth = 0

        if _recency_query(query):
            hf_results = self._search_hf_papers(query)
            for raw in hf_results[:5]:
                tokens_used += _estimate_tokens(raw.abstract)
                if tokens_used > budget_tokens * 0.9:
                    break
                papers.append(self._raw_to_finding(raw))
            if not papers:
                found, consumed = self._s2_search_safe(query, budget_tokens, tokens_used)
                papers.extend(found)
                tokens_used += consumed
        else:
            found, consumed = self._s2_search_safe(query, budget_tokens, tokens_used)
            papers.extend(found)
            tokens_used += consumed

        # Citation graph: crawl one level if budget remains
        if papers and tokens_used < budget_tokens * 0.7:
            anchor_id = papers[0].arxiv_id
            if anchor_id:
                downstream = self._citation_graph(anchor_id, budget_tokens - tokens_used)
                papers.extend(downstream)
                if downstream:
                    crawl_depth = 1

        return PapersResult(papers=tuple(papers[:20]), crawl_depth=crawl_depth)

    def _search_hf_papers(self, query: str) -> list[_RawPaper]:
        try:
            resp = httpx.get(_HF_API, params={"q": query}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("papers", [])
            return [
                _RawPaper(
                    title=item.get("title", ""),
                    arxiv_id=item.get("id") or item.get("arxivId"),
                    year=str(item.get("publishedAt", ""))[:4] or None,
                    citation_count=item.get("upvotes"),
                    abstract=item.get("summary", item.get("abstract", ""))[:800],
                    source="hf_papers",
                )
                for item in items[:10]
            ]
        except Exception as exc:
            logger.debug("HF Papers fetch failed: %s", exc)
            return []

    def _search_semantic_scholar(self, query: str) -> list[_RawPaper]:
        resp = httpx.get(
            f"{_S2_API}/paper/search",
            params={
                "query": query,
                "fields": "title,year,citationCount,abstract,externalIds",
                "limit": 10,
            },
            headers=self._s2_headers,
            timeout=_S2_TIMEOUT,
        )
        if resp.status_code == 429:
            raise Exception("429")
        resp.raise_for_status()
        return [
            _RawPaper(
                title=item.get("title", ""),
                arxiv_id=(item.get("externalIds") or {}).get("ArXiv"),
                year=item.get("year"),
                citation_count=item.get("citationCount"),
                abstract=item.get("abstract", "")[:800],
                source="semantic_scholar",
            )
            for item in resp.json().get("data", [])
        ]

    def _s2_search_safe(
        self, query: str, budget_tokens: int, tokens_already_used: int,
    ) -> tuple[list[PaperFinding], int]:
        """Return (findings, tokens_consumed_by_this_call)."""
        try:
            raws = self._search_semantic_scholar(query)
        except Exception as exc:
            logger.warning("S2 search failed (%s) — falling back to ArXiv", exc)
            raws = self._search_arxiv(query)
        findings = []
        consumed = 0
        for raw in raws[:8]:
            cost = _estimate_tokens(raw.abstract)
            if tokens_already_used + consumed + cost > budget_tokens * 0.9:
                break
            consumed += cost
            findings.append(self._raw_to_finding(raw))
        return findings, consumed

    def _citation_graph(self, arxiv_id: str, remaining_budget: int) -> list[PaperFinding]:
        if remaining_budget < 5_000:
            return []
        try:
            resp = httpx.get(
                f"{_S2_API}/paper/ARXIV:{arxiv_id}/citations",
                params={"fields": "title,year,citationCount,abstract,externalIds", "limit": 10},
                headers=self._s2_headers,
                timeout=_S2_TIMEOUT,
            )
            if resp.status_code == 429:
                return []
            resp.raise_for_status()
            results = []
            tokens_used = 0
            for item in resp.json().get("data", []):
                citing = item.get("citingPaper", {})
                abstract = citing.get("abstract", "")[:800]
                tokens_used += _estimate_tokens(abstract)
                if tokens_used > remaining_budget * 0.9:
                    break
                ext = citing.get("externalIds") or {}
                results.append(PaperFinding(
                    title=citing.get("title", ""),
                    arxiv_id=ext.get("ArXiv"),
                    year=citing.get("year"),
                    citation_count=citing.get("citationCount"),
                    key_finding="downstream citation — see abstract",
                    section_excerpts=(abstract,) if abstract else (),
                    source="semantic_scholar",
                ))
            return results
        except Exception as exc:
            logger.debug("Citation graph failed: %s", exc)
            return []

    def _search_arxiv(self, query: str) -> list[_RawPaper]:
        try:
            resp = httpx.get(
                _ARXIV_API,
                params={"search_query": f"all:{query}", "max_results": 8, "sortBy": "relevance"},
                timeout=10,
            )
            resp.raise_for_status()
            results = []
            for entry in re.findall(r"<entry>(.*?)</entry>", resp.text, re.DOTALL)[:8]:
                title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                id_m = re.search(r"<id>.*?/abs/([\w.]+)</id>", entry)
                summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                year_m = re.search(r"<published>(\d{4})", entry)
                results.append(_RawPaper(
                    title=(title_m.group(1).strip() if title_m else ""),
                    arxiv_id=(id_m.group(1) if id_m else None),
                    year=(int(year_m.group(1)) if year_m else None),
                    citation_count=None,
                    abstract=(summary_m.group(1).strip()[:800] if summary_m else ""),
                    source="arxiv",
                ))
            return results
        except Exception as exc:
            logger.debug("ArXiv search failed: %s", exc)
            return []

    def _raw_to_finding(self, raw: _RawPaper) -> PaperFinding:
        return PaperFinding(
            title=raw.title,
            arxiv_id=raw.arxiv_id,
            year=int(raw.year) if raw.year else None,
            citation_count=raw.citation_count,
            key_finding=raw.abstract[:200] if raw.abstract else "see paper",
            section_excerpts=(raw.abstract,) if raw.abstract else (),
            source=raw.source,  # type: ignore[arg-type]
        )
