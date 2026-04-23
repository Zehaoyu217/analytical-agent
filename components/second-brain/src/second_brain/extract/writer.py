from __future__ import annotations

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.schema.claim import ClaimFrontmatter


def write_claims(cfg: Config, claims: list[ClaimFrontmatter]) -> list[str]:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for claim in claims:
        path = cfg.claims_dir / f"{claim.id}.md"
        body = f"# {claim.statement.rstrip('.').rstrip()}\n"
        dump_document(path, claim.to_frontmatter_dict(), body)
        paths.append(str(path))
    return paths
