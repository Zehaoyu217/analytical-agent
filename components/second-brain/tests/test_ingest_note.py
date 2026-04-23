from __future__ import annotations

from pathlib import Path

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.note import NoteConverter


def test_matches_md_and_txt() -> None:
    c = NoteConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.md", suffix=".md", content=b""))
    assert c.matches(IngestInput.from_bytes(origin="x.txt", suffix=".txt", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))


def test_convert_md_preserves_body_and_extracts_title(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    md = b"# Planning\n\nNotes about Q2 planning."
    inp = IngestInput.from_bytes(origin="/path/plan.md", suffix=".md", content=md)
    artifacts = NoteConverter().convert(inp, folder)
    assert artifacts.title_hint == "Planning"
    assert "Notes about Q2 planning" in artifacts.processed_body
    assert len(artifacts.raw) == 1
    assert artifacts.raw[0].path == "raw/original.md"
    assert (folder.raw_dir / "original.md").exists()


def test_convert_txt_without_heading_uses_filename(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="/path/quick-thought.txt", suffix=".txt", content=b"Just a thought.")
    artifacts = NoteConverter().convert(inp, folder)
    assert artifacts.title_hint == "quick-thought"
