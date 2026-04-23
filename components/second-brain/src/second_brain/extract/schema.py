from __future__ import annotations

from typing import Any

CLAIM_KINDS = ["empirical", "theoretical", "definitional", "opinion", "prediction"]
CONFIDENCES = ["low", "medium", "high"]

CLAIM_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["statement", "kind", "confidence", "scope", "abstract"],
    "properties": {
        "statement": {"type": "string", "description": "Atomic falsifiable claim."},
        "kind": {"type": "string", "enum": CLAIM_KINDS},
        "confidence": {"type": "string", "enum": CONFIDENCES},
        "scope": {"type": "string", "description": "Where this claim applies."},
        "supports": {
            "type": "array", "items": {"type": "string"},
            "description": "List of supporting source-id fragments, e.g. 'src_X#sec-3.2'.",
            "default": [],
        },
        "contradicts": {
            "type": "array", "items": {"type": "string"}, "default": [],
        },
        "refines": {"type": "array", "items": {"type": "string"}, "default": []},
        "abstract": {"type": "string", "description": "BM25-optimized 1-2 sentence summary."},
    },
}

RECORD_CLAIMS_TOOL: dict[str, Any] = {
    "name": "record_claims",
    "description": (
        "Record atomic, falsifiable claims extracted from the source body. "
        "Every claim must be grounded in the source text."
    ),
    "input_schema": {
        "type": "object",
        "required": ["claims"],
        "properties": {
            "claims": {
                "type": "array",
                "items": CLAIM_ITEM_SCHEMA,
            },
        },
    },
}


def validate_claim_record(rec: dict[str, Any]) -> None:
    required = {"statement", "kind", "confidence", "scope", "abstract"}
    missing = required - rec.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if rec["kind"] not in CLAIM_KINDS:
        raise ValueError(f"kind must be one of {CLAIM_KINDS}")
    if rec["confidence"] not in CONFIDENCES:
        raise ValueError(f"confidence must be one of {CONFIDENCES}")
    for key in ("supports", "contradicts", "refines"):
        vals = rec.get(key, [])
        if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
            raise ValueError(f"{key} must be list[str]")
