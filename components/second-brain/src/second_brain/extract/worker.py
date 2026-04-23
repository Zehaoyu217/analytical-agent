from __future__ import annotations

from second_brain.config import Config
from second_brain.extract.claims import extract_claims
from second_brain.extract.client import ExtractorClient
from second_brain.extract.writer import write_claims
from second_brain.frontmatter import load_document
from second_brain.log import EventKind, append_event
from second_brain.schema.claim import ClaimFrontmatter


def extract_source(
    cfg: Config,
    *,
    source_id: str,
    client: ExtractorClient,
    density: str = "moderate",
    rubric: str = "",
) -> list[ClaimFrontmatter]:
    source_path = cfg.sources_dir / source_id / "_source.md"
    if not source_path.exists():
        raise FileNotFoundError(f"source not found: {source_path}")
    meta, body = load_document(source_path)
    existing_ids = {p.stem for p in cfg.claims_dir.glob("*.md") if p.parent.name != "resolutions"}
    claims = extract_claims(
        body=body,
        density=density,
        rubric=rubric,
        source_id=meta["id"],
        client=client,
        taken_ids=existing_ids,
    )
    write_claims(cfg, claims)
    append_event(
        kind=EventKind.AUTO,
        op="extract.claims",
        subject=meta["id"],
        value=f"{len(claims)} claims",
        home=cfg.home,
    )
    return claims
