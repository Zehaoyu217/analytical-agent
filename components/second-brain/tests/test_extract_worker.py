from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.extract.client import FakeExtractorClient
from second_brain.extract.worker import extract_source
from second_brain.frontmatter import dump_document
from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind


def _write_source(cfg: Config, slug: str, body: str) -> None:
    folder = cfg.sources_dir / slug
    (folder / "raw").mkdir(parents=True)
    (folder / "raw" / "original.md").write_text(body)
    sf = SourceFrontmatter(
        id=slug, title="Test", kind=SourceKind.NOTE,
        content_hash="sha256:0", ingested_at=datetime.now(UTC),
        raw=[RawArtifact(path="raw/original.md")], abstract="",
    )
    dump_document(folder / "_source.md", sf.to_frontmatter_dict(), body)


def test_extract_source_writes_claim_file(sb_home: Path) -> None:
    cfg = Config.load()
    _write_source(cfg, "src_test", "# Test\n\nBody.\n")
    client = FakeExtractorClient(canned=[
        {"statement": "Test says hello.", "kind": "empirical", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": "hi"},
    ])
    claims = extract_source(cfg, source_id="src_test", client=client,
                             density="moderate", rubric="")
    assert len(claims) == 1
    assert (cfg.claims_dir / f"{claims[0].id}.md").exists()
    # ensure supports back-refs the source
    assert claims[0].supports == ["src_test"]
