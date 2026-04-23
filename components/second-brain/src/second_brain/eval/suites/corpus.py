"""Corpus eval suite: ingest real documents, compile, reindex, and validate recall.

Fixture layout:

``manifest.yaml`` with:

cases:
  - name: short-paper
    source: ./inputs/paper.pdf
    expect:
      min_page_markers: 2
      min_chunks: 2
      min_pageful_chunk_ratio: 1.0
      summary_must_not_match: "^<!-- page:"
    queries:
      - query: efficient influence functions
        expected_kind: paper
        expected_title_contains: Influence Functions
        min_rr: 1.0
        require_chunk_evidence: true
        evidence_section_contains: Efficient influence functions
        require_page_provenance: true

`source` may also be a mapping with `url` and optional `filename`.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.eval.runner import EvalCase
from second_brain.frontmatter import load_document
from second_brain.index.chunker import read_chunk_manifest
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import ingest
from second_brain.reindex import reindex
from second_brain.research.broker import BrokerHit, broker_search
from second_brain.research.compiler import compile_center
from second_brain.research.schema import load_center_document

_yaml = YAML(typ="safe")
_PAGE_MARKER_RE = re.compile(r"<!--\s*page[: ]+\d+\s*-->", re.IGNORECASE)


class CorpusSuite:
    name = "corpus"

    def __init__(self, *, client: httpx.Client | None = None, timeout_s: float = 60.0) -> None:
        self._client = client
        self._timeout_s = timeout_s

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        manifest = _yaml.load((fixtures_dir / "manifest.yaml").read_text(encoding="utf-8"))
        cases: list[EvalCase] = []
        for spec in manifest.get("cases", []):
            cases.extend(self._run_case(cfg, fixtures_dir, spec))
        return cases

    def _run_case(self, cfg: Config, fixtures_dir: Path, spec: dict) -> list[EvalCase]:
        name = spec["name"]
        with tempfile.TemporaryDirectory(prefix="sb_eval_corpus_") as td:
            home = Path(td) / "home"
            eval_cfg = Config(home=home, sb_dir=home / ".sb")
            eval_cfg.sb_dir.mkdir(parents=True, exist_ok=True)

            path = self._materialize_source(fixtures_dir, spec["source"], Path(td))
            source_input = IngestInput.from_path(path)
            folder = ingest(source_input, cfg=eval_cfg)
            compile_center(eval_cfg)
            reindex(eval_cfg)

            source_meta, source_body = load_document(folder.source_md)
            paper_path, paper_summary = self._paper_summary_for_source(
                eval_cfg, source_id=str(source_meta["id"])
            )
            chunks = read_chunk_manifest(folder.chunk_manifest)

            out = [
                self._page_marker_case(name, source_body, spec.get("expect", {})),
                self._chunk_count_case(name, chunks, spec.get("expect", {})),
                self._pageful_ratio_case(name, chunks, spec.get("expect", {})),
                self._summary_case(name, paper_path, paper_summary, spec.get("expect", {})),
            ]
            for query_spec in spec.get("queries", []):
                out.append(self._query_case(eval_cfg, name, query_spec))
            return out

    def _materialize_source(self, fixtures_dir: Path, source_spec: str | dict, workdir: Path) -> Path:
        if isinstance(source_spec, str):
            path = Path(source_spec)
            if not path.is_absolute():
                path = fixtures_dir / source_spec
            return path

        if "path" in source_spec:
            path = Path(str(source_spec["path"]))
            if not path.is_absolute():
                path = fixtures_dir / path
            return path

        if "url" not in source_spec:
            raise ValueError("source must define either path or url")

        url = str(source_spec["url"])
        filename = str(source_spec.get("filename") or self._filename_from_url(url))
        target = workdir / filename
        client = self._client or httpx.Client(timeout=self._timeout_s)
        try:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            target.write_bytes(response.content)
        finally:
            if self._client is None:
                client.close()
        return target

    def _paper_summary_for_source(self, cfg: Config, *, source_id: str) -> tuple[Path | None, str]:
        if not cfg.papers_dir.exists():
            return None, ""
        for path in sorted(cfg.papers_dir.glob("*.md")):
            meta, _body = load_center_document(path)
            if source_id in meta.source_ids:
                return path, meta.summary
        return None, ""

    def _page_marker_case(self, name: str, body: str, expect: dict) -> EvalCase:
        count = len(_PAGE_MARKER_RE.findall(body))
        minimum = int(expect.get("min_page_markers", 0))
        return EvalCase(
            name=f"{name}: page-markers",
            passed=count >= minimum,
            metric=float(count),
            details=f"markers={count} min={minimum}",
        )

    def _chunk_count_case(self, name: str, chunks: list, expect: dict) -> EvalCase:
        minimum = int(expect.get("min_chunks", 0))
        count = len(chunks)
        return EvalCase(
            name=f"{name}: chunk-count",
            passed=count >= minimum,
            metric=float(count),
            details=f"chunks={count} min={minimum}",
        )

    def _pageful_ratio_case(self, name: str, chunks: list, expect: dict) -> EvalCase:
        minimum = float(expect.get("min_pageful_chunk_ratio", 0.0))
        if not chunks:
            ratio = 0.0
        else:
            ratio = sum(1 for chunk in chunks if chunk.page_start is not None) / len(chunks)
        return EvalCase(
            name=f"{name}: pageful-ratio",
            passed=ratio >= minimum,
            metric=ratio,
            details=f"ratio={ratio:.3f} min={minimum:.3f}",
        )

    def _summary_case(
        self, name: str, paper_path: Path | None, summary: str, expect: dict
    ) -> EvalCase:
        summary = summary.strip()
        pattern = expect.get("summary_must_not_match")
        if pattern is None:
            passed = bool(summary) and not _PAGE_MARKER_RE.fullmatch(summary)
        else:
            passed = bool(summary) and re.search(str(pattern), summary, re.IGNORECASE) is None
        location = paper_path.name if paper_path else "<missing>"
        return EvalCase(
            name=f"{name}: paper-summary",
            passed=passed,
            metric=1.0 if passed else 0.0,
            details=f"path={location} summary={summary[:120]!r}",
        )

    def _query_case(self, cfg: Config, case_name: str, spec: dict) -> EvalCase:
        query = str(spec["query"])
        k = int(spec.get("k", 5))
        results = broker_search(cfg, query=query, k=k, scope=str(spec.get("scope", "both")))
        hit, rank = self._best_match(results.hits, spec)
        rr = 0.0 if hit is None else 1.0 / rank
        passed = hit is not None and rr >= float(spec.get("min_rr", 1.0))

        if hit is not None and spec.get("require_chunk_evidence"):
            passed = passed and any(ev.kind == "chunk" for ev in hit.evidence)
        if hit is not None and spec.get("require_page_provenance"):
            passed = passed and self._has_page_provenance(hit)
        if hit is not None and spec.get("evidence_section_contains"):
            needle = str(spec["evidence_section_contains"]).lower()
            passed = passed and any(
                needle in (ev.section_title or "").lower() for ev in hit.evidence if ev.kind == "chunk"
            )

        matched = hit.id if hit is not None else "<none>"
        detail = (
            f"rr={rr:.3f} matched={matched} "
            f"top={[candidate.id for candidate in results.hits[:3]]}"
        )
        return EvalCase(
            name=f"{case_name}: query:{query}",
            passed=passed,
            metric=rr,
            details=detail,
        )

    def _best_match(self, hits: list[BrokerHit], spec: dict) -> tuple[BrokerHit | None, int]:
        for idx, hit in enumerate(hits, start=1):
            if self._matches(hit, spec):
                return hit, idx
        return None, 0

    def _matches(self, hit: BrokerHit, spec: dict) -> bool:
        if "expected_kind" in spec and hit.kind != spec["expected_kind"]:
            return False
        if "expected_id" in spec and hit.id != spec["expected_id"]:
            return False
        if "expected_id_contains" in spec and str(spec["expected_id_contains"]) not in hit.id:
            return False
        return (
            "expected_title_contains" not in spec
            or str(spec["expected_title_contains"]).lower() in hit.title.lower()
        )

    def _has_page_provenance(self, hit: BrokerHit) -> bool:
        if hit.page_start is not None:
            return True
        return any(ev.page_start is not None for ev in hit.evidence if ev.kind == "chunk")

    def _filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        name = Path(parsed.path).name
        return name or "downloaded.pdf"
