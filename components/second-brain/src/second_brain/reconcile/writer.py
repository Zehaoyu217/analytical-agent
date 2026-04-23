from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.reconcile.client import ReconcileResponse
from second_brain.reconcile.finder import OpenDebate


def _resolution_slug(debate: OpenDebate) -> str:
    left = debate.left_id.removeprefix("clm_")
    right = debate.right_id.removeprefix("clm_")
    return f"{left}__vs__{right}"


def write_resolution(cfg: Config, debate: OpenDebate, resp: ReconcileResponse) -> str:
    """Write resolutions/<slug>.md and update the primary claim's frontmatter.

    Returns the resolution path relative to cfg.home (suitable for claim.resolution).
    """
    resolutions_dir = cfg.claims_dir / "resolutions"
    resolutions_dir.mkdir(parents=True, exist_ok=True)

    slug = _resolution_slug(debate)
    note_path = resolutions_dir / f"{slug}.md"
    body = (
        f"# {debate.left_id} vs {debate.right_id}\n\n"
        f"- applies_where: {resp.applies_where}\n"
        f"- primary: {resp.primary_claim_id}\n\n"
        f"{resp.resolution_md.strip()}\n"
    )
    if resp.rationale:
        body += f"\n## Rationale\n\n{resp.rationale.strip()}\n"
    note_path.write_text(body, encoding="utf-8")

    rel = str(note_path.relative_to(cfg.home))

    primary_path = Path(debate.left_path if debate.left_id == resp.primary_claim_id
                        else debate.right_path)
    meta, md_body = load_document(primary_path)
    meta["resolution"] = rel
    dump_document(primary_path, meta, md_body)
    return rel
