from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.docx import DocxConverter


def test_matches_docx_suffix() -> None:
    c = DocxConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.docx", suffix=".docx", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))


def test_convert_writes_raw_and_returns_body(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/doc.docx", suffix=".docx", content=b"not-a-real-docx")
    artifacts = DocxConverter().convert(inp, folder)
    assert (folder.raw_dir / "original.docx").exists()
    assert len(artifacts.processed_body) > 0
    assert artifacts.raw[0].path == "raw/original.docx"
    assert artifacts.raw[0].kind == "original"


def test_guess_title_falls_back_to_origin_stem(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    # Force markitdown fallback with bytes that collapse to empty after strip.
    inp = IngestInput.from_bytes(origin="/p/my-report.docx", suffix=".docx", content=b"")
    artifacts = DocxConverter().convert(inp, folder)
    assert artifacts.title_hint == "my-report"


@pytest.mark.integration
def test_convert_real_docx_integration(tmp_path: Path) -> None:
    pytest.importorskip("markitdown")
    pytest.importorskip("docx")  # python-docx, only present under markitdown[docx]
    from docx import Document as DocxDoc

    raw_path = tmp_path / "hello.docx"
    doc = DocxDoc()
    doc.add_paragraph("Hello DOCX integration")
    doc.save(raw_path)

    folder = SourceFolder.create(tmp_path / "src_i")
    inp = IngestInput.from_path(raw_path)
    artifacts = DocxConverter().convert(inp, folder)
    assert "Hello DOCX integration" in artifacts.processed_body
