from __future__ import annotations

from pathlib import Path

from second_brain.frontmatter import dump_document, load_document


def test_load_document_parses_yaml_and_body(tmp_path: Path) -> None:
    path = tmp_path / "source.md"
    path.write_text(
        "---\n"
        "id: src_test\n"
        "title: Hello\n"
        "tags: [a, b]\n"
        "---\n"
        "\n"
        "# Heading\n\n"
        "Body text.\n"
    )
    meta, body = load_document(path)
    assert meta["id"] == "src_test"
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("\n# Heading")


def test_dump_document_writes_roundtrippable(tmp_path: Path) -> None:
    path = tmp_path / "out.md"
    dump_document(path, {"id": "src_x", "tags": ["ml"]}, "# Body\n")
    text = path.read_text()
    assert text.startswith("---\n")
    meta, body = load_document(path)
    assert meta == {"id": "src_x", "tags": ["ml"]}
    assert body == "# Body\n"


def test_load_rejects_missing_frontmatter(tmp_path: Path) -> None:
    import pytest

    path = tmp_path / "broken.md"
    path.write_text("# No frontmatter here\n")
    with pytest.raises(ValueError, match="missing frontmatter"):
        load_document(path)


def test_dump_preserves_key_order(tmp_path: Path) -> None:
    path = tmp_path / "ordered.md"
    meta = {"id": "src_z", "title": "t", "kind": "pdf", "content_hash": "sha256:abc"}
    dump_document(path, meta, "body\n")
    text = path.read_text().splitlines()
    # Keys appear in the same order we passed them
    assert text[1].startswith("id:")
    assert text[2].startswith("title:")
    assert text[3].startswith("kind:")
    assert text[4].startswith("content_hash:")
