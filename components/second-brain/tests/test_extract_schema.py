from __future__ import annotations

from second_brain.extract.schema import RECORD_CLAIMS_TOOL, validate_claim_record


def test_tool_has_expected_shape() -> None:
    assert RECORD_CLAIMS_TOOL["name"] == "record_claims"
    schema = RECORD_CLAIMS_TOOL["input_schema"]
    assert schema["type"] == "object"
    assert "claims" in schema["properties"]
    assert schema["properties"]["claims"]["type"] == "array"


def test_validate_claim_accepts_minimal_record() -> None:
    rec = {
        "statement": "x",
        "kind": "empirical",
        "confidence": "high",
        "scope": "",
        "supports": [],
        "contradicts": [],
        "refines": [],
        "abstract": "y",
    }
    validate_claim_record(rec)  # does not raise


def test_validate_claim_rejects_bad_kind() -> None:
    import pytest
    rec = {"statement": "x", "kind": "BOGUS", "confidence": "high",
           "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": ""}
    with pytest.raises(ValueError):
        validate_claim_record(rec)
