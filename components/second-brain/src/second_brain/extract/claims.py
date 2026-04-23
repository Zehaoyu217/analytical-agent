from __future__ import annotations

import logging
from datetime import UTC, datetime

from slugify import slugify

from second_brain.extract.client import ExtractorClient, ExtractRequest
from second_brain.extract.schema import validate_claim_record
from second_brain.schema.claim import (
    ClaimConfidence,
    ClaimFrontmatter,
    ClaimKind,
    ClaimStatus,
)

log = logging.getLogger(__name__)


def extract_claims(
    *,
    body: str,
    density: str,
    rubric: str,
    source_id: str,
    client: ExtractorClient,
    taken_ids: set[str] | None = None,
) -> list[ClaimFrontmatter]:
    taken = set(taken_ids or ())
    resp = client.extract(ExtractRequest(
        body=body, density=density, rubric=rubric, source_id=source_id,
    ))
    results: list[ClaimFrontmatter] = []
    now = datetime.now(UTC)
    for rec in resp.claims:
        try:
            validate_claim_record(rec)
        except ValueError as exc:
            log.warning("discarding invalid claim from %s: %s", source_id, exc)
            continue
        claim_id = _propose_id(rec["statement"], taken=taken)
        taken.add(claim_id)
        supports = list(rec.get("supports") or [])
        # If the extractor emitted bare '#section' fragments, anchor them to source_id.
        supports = [_anchor_to_source(s, source_id) for s in supports]
        if not supports:
            supports = [source_id]
        results.append(ClaimFrontmatter(
            id=claim_id,
            statement=rec["statement"],
            kind=ClaimKind(rec["kind"]),
            confidence=ClaimConfidence(rec["confidence"]),
            scope=rec.get("scope", ""),
            supports=supports,
            contradicts=list(rec.get("contradicts") or []),
            refines=list(rec.get("refines") or []),
            extracted_at=now,
            status=ClaimStatus.ACTIVE,
            resolution=None,
            abstract=rec.get("abstract", ""),
        ))
    return results


def _propose_id(statement: str, *, taken: set[str]) -> str:
    stem = slugify(statement, max_length=60, lowercase=True) or "claim"
    base = f"clm_{stem}"
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _anchor_to_source(ref: str, source_id: str) -> str:
    if ref.startswith("#"):
        return f"{source_id}{ref}"
    return ref
