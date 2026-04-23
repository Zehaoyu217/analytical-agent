from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.pdf import PdfConverter


@pytest.fixture
def tiny_pdf_bytes() -> bytes:
    """Minimal one-page PDF with the text 'Hello PDF'."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 100 Td (Hello PDF) Tj ET\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n"
        b"0000000099 00000 n \n0000000193 00000 n \n0000000274 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n330\n%%EOF\n"
    )


def test_matches_pdf_suffix() -> None:
    c = PdfConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.md", suffix=".md", content=b""))


def test_convert_writes_raw_and_returns_body(tmp_path: Path, tiny_pdf_bytes: bytes) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/tiny.pdf", suffix=".pdf", content=tiny_pdf_bytes)
    artifacts = PdfConverter().convert(inp, folder)
    assert (folder.raw_dir / "original.pdf").exists()
    assert len(artifacts.processed_body) > 0
    assert artifacts.raw[0].path == "raw/original.pdf"


def test_extract_text_requests_page_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_convert(**kwargs: object) -> None:
        calls.update(kwargs)
        out = Path(str(kwargs["output_dir"])) / "paper.md"
        out.write_text(
            "# Attention Study\n\n<!-- page: 1 -->\nFirst page.\n\n<!-- page: 2 -->\nSecond page.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("second_brain.ingest.pdf._ensure_java_on_path", lambda: None)
    monkeypatch.setitem(sys.modules, "opendataloader_pdf", SimpleNamespace(convert=fake_convert))

    inp = IngestInput.from_bytes(origin="/p/paper.pdf", suffix=".pdf", content=b"%PDF")
    body = PdfConverter._extract_text(inp)

    assert calls["format"] == "markdown"
    assert calls["markdown_page_separator"] == "<!-- page: %page-number% -->"
    assert "<!-- page: 1 -->" in body
    assert "<!-- page: 2 -->" in body


def test_guess_title_skips_page_marker_lines() -> None:
    inp = IngestInput.from_bytes(origin="/p/attention-notes.pdf", suffix=".pdf", content=b"")
    body = "\n".join(
        [
            "<!-- page: 1 -->",
            "Attention Is Useful",
            "",
        ]
    )
    assert PdfConverter._guess_title(body, inp) == "Attention Is Useful"


@pytest.mark.integration
def test_convert_extracts_text(tmp_path: Path) -> None:
    """Real-world PDF integration test.

    The hand-rolled minimal PDF in the unit fixture is too malformed for
    opendataloader's stricter parser to handle (it succeeded with the old
    pdfminer pipeline, which was looser). This test uses a real PDF
    sample shipped with the repo to verify end-to-end extraction.
    """
    sample = Path(__file__).parent / "fixtures" / "hello.pdf"
    if not sample.exists():
        pytest.skip("sample PDF fixture missing")
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_path(sample)
    artifacts = PdfConverter().convert(inp, folder)
    assert artifacts.processed_body.strip()
    assert "[opendataloader_pdf" not in artifacts.processed_body
