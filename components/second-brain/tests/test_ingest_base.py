from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder


def test_ingest_input_from_local_path(tmp_path: Path) -> None:
    f = tmp_path / "note.md"
    f.write_text("hello")
    inp = IngestInput.from_path(f)
    assert inp.origin == str(f)
    with inp.open_stream() as stream:
        assert stream.read() == b"hello"
    assert inp.suffix == ".md"


def test_source_folder_create_and_paths(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "sources" / "src_x")
    assert folder.raw_dir.exists()
    assert folder.source_md == tmp_path / "sources" / "src_x" / "_source.md"
    assert folder.raw_manifest == tmp_path / "sources" / "src_x" / "raw_manifest.json"


def test_source_folder_refuses_existing(tmp_path: Path) -> None:
    (tmp_path / "sources" / "src_x").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        SourceFolder.create(tmp_path / "sources" / "src_x")
