from __future__ import annotations

from second_brain.index.chunker import build_chunks


def test_build_chunks_preserves_section_and_page_span() -> None:
    body = "\n".join(
        [
            "# Intro",
            "",
            "<!-- page: 1 -->",
            "First paragraph about attention.",
            "",
            "Second paragraph about sequence transduction.",
            "",
            "# Results",
            "",
            "<!-- page: 2 -->",
            "Metrics improved on the validation split.",
            "",
        ]
    )
    chunks = build_chunks("src_attention", body, max_chars=80, min_chars=20)
    assert len(chunks) >= 2
    assert chunks[0].section_title == "Intro"
    assert chunks[0].page_start == 1
    assert any(chunk.page_start == 2 for chunk in chunks)
