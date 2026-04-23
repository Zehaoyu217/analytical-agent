from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import DEFAULT_CONVERTERS, ingest


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def test_default_converter_kinds_cover_v1() -> None:
    kinds = {c.kind for c in DEFAULT_CONVERTERS}
    assert {"note", "pdf", "url", "repo", "docx", "epub"}.issubset(kinds)


def test_dispatches_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    inp = IngestInput.from_bytes(origin="/p/doc.docx", suffix=".docx", content=b"x")
    folder = ingest(inp, cfg=cfg)
    assert (folder.root / "raw" / "original.docx").exists()
    assert (folder.root / "_source.md").exists()


def test_dispatches_epub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    inp = IngestInput.from_bytes(origin="/p/book.epub", suffix=".epub", content=b"x")
    folder = ingest(inp, cfg=cfg)
    assert (folder.root / "raw" / "original.epub").exists()
