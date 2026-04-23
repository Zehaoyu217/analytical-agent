from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalRunner
from second_brain.eval.suites.corpus import CorpusSuite


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_corpus_suite_passes_on_stubbed_pdf(sb_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 stub")

    fixtures = tmp_path / "fixtures" / "corpus"
    fixtures.mkdir(parents=True)
    (fixtures / "manifest.yaml").write_text(
        "\n".join(
            [
                "cases:",
                "  - name: sample-paper",
                f"    source: {pdf_path}",
                "    expect:",
                "      min_page_markers: 2",
                "      min_chunks: 2",
                "      min_pageful_chunk_ratio: 1.0",
                "      summary_must_not_match: '^<!-- page:'",
                "    queries:",
                "      - query: efficient influence functions",
                "        expected_kind: paper",
                "        expected_title_contains: Causal Inference Notes",
                "        min_rr: 1.0",
                "        require_chunk_evidence: true",
                "        evidence_section_contains: Efficient influence functions in the actual model",
                "        require_page_provenance: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    body = "\n".join(
        [
            "<!-- page: 1 -->",
            "",
            "# Causal Inference Notes",
            "",
            "Abstract",
            "",
            (
                "This note explains efficient influence functions and doubly robust "
                "estimation for causal inference under sample selection."
            ),
            "",
            "### 1 Introduction",
            "",
            (
                "Causal inference under selection requires careful modeling of "
                "treatment assignment and observability. " * 8
            ),
            "",
            "<!-- page: 2 -->",
            "",
            "### 7 Efficient influence functions in the actual model",
            "",
            (
                "Efficient influence functions produce doubly robust estimators and "
                "support debiased causal effect estimation in practical workflows. " * 8
            ),
            "",
        ]
    )
    monkeypatch.setattr(
        "second_brain.ingest.pdf.PdfConverter._extract_text",
        staticmethod(lambda source: body),
    )

    cfg = Config.load()
    runner = EvalRunner(cfg, {"corpus": CorpusSuite()})
    report = runner.run("corpus", fixtures)

    assert report.cases
    assert report.passed, [c for c in report.cases if not c.passed]
    assert any(case.name.endswith("page-markers") for case in report.cases)
    assert any("query:efficient influence functions" in case.name for case in report.cases)
