from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.ingest.retry import RetryError, retry_source


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _make_failed_source(home: Path, slug: str, raw_filename: str, body: bytes) -> Path:
    folder = home / "sources" / slug
    (folder / "raw").mkdir(parents=True)
    raw_path = folder / "raw" / raw_filename
    raw_path.write_bytes(body)
    fm = {
        "id": slug,
        "title": slug,
        "kind": "failed",
        "content_hash": "sha256-placeholder",
        "raw": [{"path": f"raw/{raw_filename}", "kind": "note", "sha256": "x"}],
        "ingested_at": "2026-04-18T00:00:00Z",
    }
    dump_document(folder / "_source.md", fm, "retry me")
    return folder


def test_retry_source_succeeds_and_flips_kind(sb_home: Path):
    folder_path = _make_failed_source(
        sb_home, "src_note_sample_1", "note.md", b"# Good\n\nretryable content.\n"
    )
    cfg = Config.load()
    retry_source("src_note_sample_1", cfg=cfg)

    fm, body = load_document(folder_path / "_source.md")
    assert fm["kind"] == "note"
    assert "retryable content" in body


def test_retry_source_raises_when_slug_missing(sb_home: Path):
    cfg = Config.load()
    with pytest.raises(RetryError, match="not found"):
        retry_source("nope", cfg=cfg)


def test_retry_source_raises_when_raw_missing(sb_home: Path):
    folder = sb_home / "sources" / "src_broken"
    folder.mkdir()
    dump_document(
        folder / "_source.md",
        {
            "id": "src_broken",
            "title": "broken",
            "kind": "failed",
            "content_hash": "sha256-placeholder",
            "ingested_at": "2026-04-18T00:00:00Z",
            "raw": [],
        },
        "",
    )
    cfg = Config.load()
    with pytest.raises(RetryError, match="no raw"):
        retry_source("src_broken", cfg=cfg)
