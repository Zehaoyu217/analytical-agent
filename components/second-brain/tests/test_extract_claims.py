from __future__ import annotations

from second_brain.extract.claims import extract_claims
from second_brain.extract.client import FakeExtractorClient


def test_extract_claims_passes_through() -> None:
    client = FakeExtractorClient(canned=[
        {"statement": "Attention replaces recurrence.", "kind": "empirical",
         "confidence": "high", "scope": "seq2seq",
         "supports": [], "contradicts": [], "refines": [], "abstract": "attn vs rnn"},
    ])
    claims = extract_claims(
        body="irrelevant", density="moderate", rubric="",
        source_id="src_a", client=client,
    )
    assert len(claims) == 1
    assert claims[0].statement == "Attention replaces recurrence."
    assert claims[0].id.startswith("clm_")


def test_skips_invalid_records() -> None:
    client = FakeExtractorClient(canned=[
        {"statement": "ok", "kind": "empirical", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": ""},
        {"statement": "bad", "kind": "NOT_A_KIND", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": ""},
    ])
    claims = extract_claims(
        body="", density="moderate", rubric="", source_id="src_x", client=client,
    )
    assert len(claims) == 1
