from __future__ import annotations

from second_brain.schema.source import SourceKind
from second_brain.slugs import propose_source_slug


def test_slug_from_title_with_year() -> None:
    slug = propose_source_slug(kind=SourceKind.PDF, title="Attention Is All You Need", year=2017)
    assert slug == "src_2017_attention-is-all-you-need"


def test_slug_from_title_without_year() -> None:
    slug = propose_source_slug(kind=SourceKind.NOTE, title="Planning Doc")
    assert slug == "src_planning-doc"


def test_slug_truncates_to_max_length() -> None:
    long_title = " ".join(["word"] * 40)
    slug = propose_source_slug(kind=SourceKind.PDF, title=long_title, max_length=40)
    assert len(slug) <= 40
    assert slug.startswith("src_")


def test_slug_avoids_collision_by_appending_digit(tmp_path) -> None:
    # Simulate prior collision: caller passes `taken` set.
    taken = {"src_planning-doc"}
    slug = propose_source_slug(kind=SourceKind.NOTE, title="Planning Doc", taken=taken)
    assert slug == "src_planning-doc-2"
