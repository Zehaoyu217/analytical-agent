from pathlib import Path

from backend.app.integrity.plugins.doc_audit.parser.markdown import (
    Heading,
    MarkdownLink,
    parse_doc,
    slug_for_heading,
)


def test_slug_for_heading_lowercases_and_hyphenates():
    assert slug_for_heading("My Section") == "my-section"
    assert slug_for_heading("API / Routes") == "api--routes"
    assert slug_for_heading("Hello, World!") == "hello-world"
    assert slug_for_heading("  Trim Me  ") == "trim-me"
    assert slug_for_heading("Numbers 123 OK") == "numbers-123-ok"


def test_parse_doc_extracts_headings_and_links(tmp_path: Path):
    md = tmp_path / "sample.md"
    md.write_text(
        "---\nstatus: accepted\n---\n\n"
        "# Top Heading\n\n"
        "Some prose with [a link](other.md) and an [anchor link](other.md#section).\n\n"
        "## Sub Heading\n\n"
        "Another [absolute](https://example.com/x) and an [in-page](#top-heading).\n\n"
        "```python\n"
        "# This code block should not produce link extractions\n"
        "[fake](should-not-extract.md)\n"
        "```\n",
        encoding="utf-8",
    )

    parsed = parse_doc(md, rel_path="sample.md")

    assert parsed.rel_path == "sample.md"
    assert parsed.front_matter == {"status": "accepted"}
    assert any(h.text == "Top Heading" and h.slug == "top-heading" and h.level == 1 for h in parsed.headings)
    assert any(h.text == "Sub Heading" and h.slug == "sub-heading" and h.level == 2 for h in parsed.headings)

    targets = [(link.target, link.anchor) for link in parsed.links]
    assert ("other.md", None) in targets
    assert ("other.md", "section") in targets
    assert ("https://example.com/x", None) in targets
    assert ("", "top-heading") in targets
    assert not any("should-not-extract.md" in (link.target or "") for link in parsed.links)


def test_parse_doc_handles_missing_front_matter(tmp_path: Path):
    md = tmp_path / "plain.md"
    md.write_text("# Hello\n\nNo front matter here.\n", encoding="utf-8")
    parsed = parse_doc(md, rel_path="plain.md")
    assert parsed.front_matter == {}
    assert parsed.headings[0].text == "Hello"
