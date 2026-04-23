from __future__ import annotations

from typing import Any

APPLIES_WHERE = ["scope", "methodology", "era", "definition", "interpretation", "reject"]

RECORD_RESOLUTION_TOOL: dict[str, Any] = {
    "name": "record_resolution",
    "description": (
        "Record a resolution for a pair of contradicting claims. Explain why they "
        "disagree, pick which claim is primary in the current context, and name "
        "the dimension along which they differ (scope, methodology, era, etc.)."
    ),
    "input_schema": {
        "type": "object",
        "required": ["resolution_md", "applies_where", "primary_claim_id"],
        "properties": {
            "resolution_md": {
                "type": "string",
                "description": "Markdown body for claims/resolutions/<slug>.md.",
            },
            "applies_where": {"type": "string", "enum": APPLIES_WHERE},
            "primary_claim_id": {"type": "string"},
            "rationale": {"type": "string", "default": ""},
        },
    },
}


def validate_resolution_record(rec: dict[str, Any]) -> None:
    required = {"resolution_md", "applies_where", "primary_claim_id"}
    missing = required - rec.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if rec["applies_where"] not in APPLIES_WHERE:
        raise ValueError(f"applies_where must be one of {APPLIES_WHERE}")
    for key in ("resolution_md", "primary_claim_id"):
        if not isinstance(rec[key], str) or not rec[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
