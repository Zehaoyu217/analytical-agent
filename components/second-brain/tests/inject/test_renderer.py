from second_brain.index.retriever import RetrievalHit
from second_brain.inject.renderer import render_injection_block


def _hit(i: int, kind: str = "claim", score: float = 0.87,
         neighbors: list[str] | None = None) -> RetrievalHit:
    return RetrievalHit(
        id=f"clm_demo-{i}",
        kind=kind,  # type: ignore[arg-type]
        score=score,
        matched_field="statement",
        snippet=f"Self-attention is sufficient for seq transduction #{i}.",
        neighbors=neighbors or [],
    )


def test_renders_header_numbered_list_and_footer():
    out = render_injection_block([_hit(1, neighbors=["src_a", "clm_b"])])
    assert out.startswith("### Second Brain — top matches for this prompt")
    assert "1. [clm_demo-1] (score 0.87)" in out
    assert "Self-attention is sufficient for seq transduction #1." in out
    assert "◇ neighbor: src_a" in out
    assert "◇ neighbor: clm_b" in out
    assert "Use sb_load(<id>, depth=1) to expand any of these." in out


def test_returns_empty_string_when_no_hits():
    assert render_injection_block([]) == ""


def test_budget_truncation_drops_tail_items_but_keeps_header():
    hits = [_hit(i) for i in range(1, 21)]
    out = render_injection_block(hits, max_tokens=80)  # tiny budget
    # Header always present, tail items dropped, explicit truncation note.
    assert out.startswith("### Second Brain — top matches for this prompt")
    assert "truncated" in out.lower()
    # At least one hit must have survived.
    assert "1. [clm_demo-1]" in out
