from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest


def test_ingest_note_creates_folder(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/hello.md", suffix=".md", content=b"# Hello\n\nBody.")
    folder = ingest(inp, cfg=cfg)
    assert folder.source_md.exists()
    meta, body = load_document(folder.source_md)
    assert meta["id"].startswith("src_")
    assert meta["title"] == "Hello"
    assert meta["kind"] == "note"
    assert "Body." in body


def test_ingest_rejects_unknown_suffix(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/x.weird", suffix=".weird", content=b"")
    with pytest.raises(IngestError, match="no converter matched"):
        ingest(inp, cfg=cfg)


def test_ingest_dedupes_on_content_hash(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/a.md", suffix=".md", content=b"# Hello\n\nBody.")
    first = ingest(inp, cfg=cfg)
    with pytest.raises(IngestError, match="duplicate"):
        ingest(inp, cfg=cfg)
    assert first.source_md.exists()


def test_ingest_writes_raw_manifest(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/note.md", suffix=".md", content=b"# X\n\ncontent")
    folder = ingest(inp, cfg=cfg)
    import json
    manifest = json.loads(folder.raw_manifest.read_text())
    assert manifest[0]["kind"] == "original"
    assert manifest[0]["path"].startswith("raw/")
