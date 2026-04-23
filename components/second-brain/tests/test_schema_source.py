from __future__ import annotations

from datetime import UTC, datetime

import pytest

from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind


def test_minimal_source_validates() -> None:
    sf = SourceFrontmatter(
        id="src_test",
        title="Test",
        kind=SourceKind.NOTE,
        content_hash="sha256:abc",
        ingested_at=datetime(2026, 4, 17, tzinfo=UTC),
        raw=[RawArtifact(path="raw/note.md", kind="original", sha256="sha256:abc")],
        abstract="A one-line abstract.",
    )
    assert sf.kind == SourceKind.NOTE
    assert sf.cites == []
    assert sf.related == []
    assert sf.supersedes == []
    assert sf.tags == []


def test_id_must_be_prefixed() -> None:
    with pytest.raises(ValueError, match="must start with 'src_'"):
        SourceFrontmatter(
            id="oops",
            title="x",
            kind=SourceKind.NOTE,
            content_hash="sha256:abc",
            ingested_at=datetime(2026, 4, 17, tzinfo=UTC),
            raw=[],
            abstract="",
        )


def test_roundtrip_via_dict() -> None:
    sf = SourceFrontmatter(
        id="src_a",
        title="A",
        kind=SourceKind.PDF,
        authors=["Smith, J."],
        year=2024,
        content_hash="sha256:0",
        ingested_at=datetime(2026, 4, 17, tzinfo=UTC),
        habit_taxonomy="papers/ml",
        raw=[RawArtifact(path="raw/a.pdf", kind="original", sha256="sha256:0")],
        cites=["src_b"],
        abstract="Short.",
    )
    dumped = sf.to_frontmatter_dict()
    restored = SourceFrontmatter.from_frontmatter_dict(dumped)
    assert restored == sf
