from __future__ import annotations

from dataclasses import dataclass, field

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.schema.claim import ClaimFrontmatter
from second_brain.schema.source import SourceFrontmatter


@dataclass(frozen=True)
class KBSnapshot:
    sources: dict[str, SourceFrontmatter] = field(default_factory=dict)
    claims: dict[str, ClaimFrontmatter] = field(default_factory=dict)

    @property
    def all_ids(self) -> set[str]:
        return set(self.sources.keys()) | set(self.claims.keys())


def load_snapshot(cfg: Config) -> KBSnapshot:
    sources: dict[str, SourceFrontmatter] = {}
    claims: dict[str, ClaimFrontmatter] = {}

    if cfg.sources_dir.exists():
        for source_md in sorted(cfg.sources_dir.glob("*/_source.md")):
            meta, _ = load_document(source_md)
            fm = SourceFrontmatter.model_validate(meta)
            sources[fm.id] = fm

    if cfg.claims_dir.exists():
        for claim_md in sorted(cfg.claims_dir.glob("*.md")):
            meta, _ = load_document(claim_md)
            fm = ClaimFrontmatter.model_validate(meta)
            claims[fm.id] = fm

    return KBSnapshot(sources=sources, claims=claims)
