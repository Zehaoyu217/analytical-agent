from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.epub import EpubConverter


def test_matches_epub_suffix() -> None:
    c = EpubConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.epub", suffix=".epub", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))


def test_convert_writes_raw_and_returns_body(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/book.epub", suffix=".epub", content=b"")
    artifacts = EpubConverter().convert(inp, folder)
    assert (folder.raw_dir / "original.epub").exists()
    assert len(artifacts.processed_body) > 0
    assert "[markitdown failed" in artifacts.processed_body
    assert artifacts.raw[0].path == "raw/original.epub"


def test_guess_title_falls_back_to_origin_stem(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="/p/ulysses.epub", suffix=".epub", content=b"")
    artifacts = EpubConverter().convert(inp, folder)
    assert artifacts.title_hint == "ulysses"


@pytest.mark.integration
def test_convert_real_epub_integration(tmp_path: Path) -> None:
    pytest.importorskip("markitdown")
    pytest.importorskip("ebooklib")  # only present under markitdown[epub]
    # Integration smoke: building a real epub is involved; rely on fixture if ever added.
    pytest.skip("real epub fixture not provided; marker reserved for CI image with markitdown[epub]")
